"""Day-one test. Proves the pipeline runs something real, not an empty suite."""

import json

from app.api import application


def call(path: str, method: str = "GET") -> tuple[int, dict]:
    """Drive the WSGI app directly -- no server, no socket."""
    captured: dict[str, str] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(application({"PATH_INFO": path, "REQUEST_METHOD": method}, start_response))
    code = int(captured["status"].split(" ", 1)[0])
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
