"""One-match online QA client. Human actions are supplied explicitly by the tester.

Only authenticated P1 observations are shown during play. Credentials stay in a
mode-0600 temporary file and are never written to the review artifacts.
"""
import json
import os
from pathlib import Path
import sys
import time

import httpx

BASE = "http://127.0.0.1:8019"
SESSION = Path(os.environ.get("PALERMO_TEST_SESSION", "/private/tmp/palermo-luna-online-20261002.json"))
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent / "live-luna"


def save_session(data):
    descriptor = os.open(SESSION, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(data, handle)


def record(game_id, kind, data):
    OUTPUT.mkdir(exist_ok=True)
    with (OUTPUT / f"{game_id}.jsonl").open("a") as handle:
        handle.write(json.dumps({"type": kind, "time": time.time(), **data}, ensure_ascii=False) + "\n")


def main():
    command = sys.argv[1]
    with httpx.Client(base_url=BASE, timeout=15) as client:
        if command == "start":
            if SESSION.exists():
                raise SystemExit("An online session already exists; use poll rather than starting another match.")
            response = client.post("/games/interactive", json={"character_id": 1, "language": "fa", "ai_mode": "luna"})
            response.raise_for_status()
            created = response.json()
            session = {"game_id": created["game_id"], "token": created["human"]["token"], "cursor": 0, "started": time.time()}
            save_session(session)
            safe = {key: created[key] for key in ("game_id", "ai_mode", "ai_model", "status")}
            print(json.dumps(safe))
            record(session["game_id"], "CREATED", safe)
        else:
            session = json.loads(SESSION.read_text())
        game_id = session["game_id"]
        headers = {"X-Player-Token": session["token"]}
        if command == "act":
            payload = json.loads(sys.argv[2])
            response = client.post(f"/game/{game_id}/interactive/action", headers=headers, json=payload)
            response.raise_for_status()
            record(game_id, "HUMAN_ACTION", {"payload": payload})
            print(json.dumps({"accepted": payload["action"]}))
        deadline = time.monotonic() + (float(sys.argv[2]) if command == "poll" and len(sys.argv) > 2 else 0)
        while True:
            run = client.get(f"/game/{game_id}/run-state", headers=headers)
            run.raise_for_status()
            run = run.json()
            if run["status"] not in {"QUEUED", "RUNNING"} or time.monotonic() >= deadline:
                break
            time.sleep(1)
        observation = client.get(f"/game/{game_id}/player/P1/observation", headers=headers)
        observation.raise_for_status()
        observation = observation.json()
        new_events = observation["events"][session["cursor"]:]
        session["cursor"] = len(observation["events"])
        save_session(session)
        view = {
            "game_id": game_id, "run": run,
            "public": observation["public_state"], "private": observation["private_state"],
            "actions": observation["available_actions"], "names": observation["player_names"],
            "new_events": new_events,
        }
        record(game_id, "OBSERVATION", view)
        if os.environ.get("PALERMO_COMPACT"):
            view["public"].pop("players", None)
            view.pop("names", None)
        print(json.dumps(view, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
