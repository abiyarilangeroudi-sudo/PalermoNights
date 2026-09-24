from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import app


def test_offline_ai_game_lifecycle_and_public_stream():
    with TestClient(app) as client:
        created_response = client.post(
            "/games/ai",
            json={"mode": "offline", "seed": 42, "live_action_budget": 1},
        )
        assert created_response.status_code == 202
        created = created_response.json()
        assert "player_credentials" not in created

        run_state = None
        for _ in range(40):
            run_state = client.get(created["run_state_url"]).json()
            if run_state["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                break
            time.sleep(0.025)
        assert run_state is not None
        assert run_state["status"] == "COMPLETED"
        assert run_state["summary"]["actions"] > 0

        public = client.get(created["public_state_url"]).json()
        assert public["phase"] == "GAME_OVER"
        assert public["winner"] in {"MAFIA", "CITIZEN"}

        with client.stream("GET", created["stream_url"]) as response:
            stream = "".join(response.iter_text())
        assert response.status_code == 200
        assert "event: game-event" in stream
        assert "event: run-state" in stream
        assert "event: stream-end" in stream
        assert "INVESTIGATION_RESULT" not in stream


def test_frontend_is_served_and_root_redirects():
    with TestClient(app, follow_redirects=False) as client:
        root = client.get("/")
        assert root.status_code in {302, 307}
        assert root.headers["location"] == "/ui/"
        ui = client.get("/ui/")
        assert ui.status_code == 200
        assert "شب‌های پالرمو" in ui.text
