from sleeper_draft_plan_companion import api


def test_board_uses_repository_strength_preferences_not_query_overrides(monkeypatch):
    configured = {
        "alpha": 0.3,
        "beta_QB": 1.0,
        "beta_RB": 1.0,
        "beta_WR": 1.0,
        "beta_TE": 1.0,
    }
    seen = {}

    monkeypatch.setattr(
        api.config,
        "draft_identity",
        lambda: {"draft_id": "default", "username": "tester"},
    )
    monkeypatch.setattr(api.preferences, "load_general_preferences", lambda: configured)

    def fake_build_board(draft_id, username=None, fresh=False, strength_parameters=None):
        seen.update(
            draft_id=draft_id,
            username=username,
            fresh=fresh,
            strength_parameters=strength_parameters,
        )
        return {"ranked": []}

    monkeypatch.setattr(api.board_module, "build_board", fake_build_board)
    monkeypatch.setattr(
        api.preferences,
        "apply_player_preferences",
        lambda payload: payload.update(preferences_applied=True) or payload,
    )

    payload = api.board(
        {
            "draft_id": "chosen",
            "fresh": "1",
            "alpha": "9.9",
            "beta_RB": "9.9",
        }
    )

    assert seen == {
        "draft_id": "chosen",
        "username": "tester",
        "fresh": True,
        "strength_parameters": configured,
    }
    assert payload["preferences_applied"] is True
    assert payload["configured"] is True
