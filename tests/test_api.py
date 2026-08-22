"""Day-one test. Proves the pipeline runs something real, not an empty suite."""

import json

from sleeper_draft_plan_companion.api import application


def call_raw(path: str, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    """Drive the WSGI app directly -- no server, no socket."""
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(application({"PATH_INFO": path, "REQUEST_METHOD": method}, start_response))
    code = int(str(captured["status"]).split(" ", 1)[0])
    headers = {k.lower(): v for k, v in captured["headers"]}
    return code, headers, body


def call(path: str, method: str = "GET") -> tuple[int, dict]:
    """As call_raw, but for the JSON endpoints."""
    code, _headers, body = call_raw(path, method)
    return code, json.loads(body)


def test_health_is_ok():
    code, payload = call("/health")
    assert code == 200
    assert payload == {"status": "ok"}


def test_unknown_path_is_404():
    code, payload = call("/nope")
    assert code == 404
    assert payload["path"] == "/nope"


def test_write_methods_are_rejected():
    code, _ = call("/health", method="POST")
    assert code == 405


def test_root_serves_the_ui():
    code, headers, body = call_raw("/")
    assert code == 200
    assert headers["content-type"].startswith("text/html")
    assert b"Draft Plan Companion" in body


def test_static_assets_are_served_with_their_own_content_type():
    for path, expected in (("/ui/styles.css", "text/css"), ("/ui/script.js", "javascript")):
        code, headers, _body = call_raw(path)
        assert code == 200, path
        assert expected in headers["content-type"], (path, headers["content-type"])


def test_missing_static_file_is_404():
    code, payload = call("/ui/does-not-exist.css")
    assert code == 404
    assert payload["error"] == "not found"


def test_traversal_outside_the_ui_directory_is_refused():
    """`/ui/../pyproject.toml` resolves to a real file -- the containment check,
    not the existence check, is what has to reject it."""
    code, _payload = call("/ui/../pyproject.toml")
    assert code == 404


def test_health_still_wins_over_static():
    code, payload = call("/health")
    assert code == 200
    assert payload == {"status": "ok"}


def test_players_summary_reports_counts(monkeypatch):
    from sleeper_draft_plan_companion import sleeper

    monkeypatch.setattr(
        sleeper,
        "load_players",
        lambda **_: ({"1": {"position": "RB", "active": True}}, 1_000_000.0),
    )

    code, payload = call("/players/summary")

    assert code == 200
    assert payload["by_position"]["RB"] == 1
    assert payload["fetched_at"] == 1_000_000.0
    assert payload["age_seconds"] > 0


def test_players_summary_is_503_when_sleeper_is_unreachable(monkeypatch):
    """A dead upstream must not look like an empty player pool."""
    from sleeper_draft_plan_companion import sleeper

    def boom(**_):
        raise OSError("connection refused")

    monkeypatch.setattr(sleeper, "load_players", boom)

    code, payload = call("/players/summary")

    assert code == 503
    assert payload["error"] == "upstream_unavailable"
    assert "connection refused" in payload["detail"]
