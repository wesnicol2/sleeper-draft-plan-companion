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
    pool_seen = {}

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
        api.sleeper,
        "load_players",
        lambda: ({"kicker": {"position": "K", "active": True}}, 123.0),
    )
    monkeypatch.setattr(
        api.draft,
        "get_picks",
        lambda draft_id, fresh=False: [{"player_id": "taken"}],
    )

    def fake_special_pool(players, taken_ids):
        pool_seen.update(players=players, taken_ids=taken_ids)
        return [{"player_id": "kicker", "position": "K"}]

    monkeypatch.setattr(
        api.preferences,
        "build_dart_throw_special_pool",
        fake_special_pool,
    )
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
    assert pool_seen == {
        "players": {"kicker": {"position": "K", "active": True}},
        "taken_ids": {"taken"},
    }
    assert payload["dart_throw_pool"] == [{"player_id": "kicker", "position": "K"}]
    assert payload["preferences_applied"] is True
    assert payload["configured"] is True
