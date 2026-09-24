# Palermo Nights

A server-authoritative backend for the seven-player hidden-information game in the supplied v1.0 specification. Humans and AI agents use the same authenticated action API; neither can mutate authoritative state or read hidden game truth.

## Implemented rules

- Exactly seven players: Mafia Boss, Mafia Deputy, Doctor, Detective, and three Citizens.
- Night 1 Mafia strategy selection, followed by public (and bluffable) role claims.
- Random, turn-based day discussion with public questions and mandatory post-round answers.
- Day 1 shunning; Day 2+ elimination, role reveal, and last-will reveal.
- Private, engine-owned trust changes with clamping to `1..100`.
- Doctor protection, Detective investigation, Boss/Deputy kill succession, and atomic night resolution.
- Immediate Citizen/Mafia win checks, including Mafia parity.
- Public, private-player, Mafia-only, and engine-only event visibility.
- Per-player bearer secrets through the `X-Player-Token` header.

AI memory, beliefs, hypotheses, and strategy selection remain outside the engine by design.

## Run locally

Python 3.11+ is required.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m app
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## API flow

Create a game:

```http
POST /games
Content-Type: application/json

{
  "player_types": ["HUMAN", "AI", "AI", "HUMAN", "AI", "AI", "HUMAN"],
  "seed": 42
}
```

The creation response returns each player's token once. Private endpoints and actions require the matching header:

```http
X-Player-Token: <player token>
```

Core endpoints:

```text
GET  /game/{game_id}/public-state
GET  /game/{game_id}/player/{player_id}/private-state
GET  /game/{game_id}/player/{player_id}/available-actions
POST /game/{game_id}/player/{player_id}/action
GET  /game/{game_id}/events
```

Ask `available-actions` before submitting an action. The action endpoint accepts the common action envelope and validates phase, identity, role, life/shun status, target, and rule-specific fields. For example:

```json
{
  "action": "SUBMIT_VOTE_DECISION",
  "vote_target": "P6",
  "suspect_2": "P3",
  "trusted_player": "P2"
}
```

To retrieve player-visible events (public plus authorized private/Mafia events), use:

```text
GET /game/{game_id}/events?player_id=P4
X-Player-Token: <P4 token>
```

Without a player identity, the event endpoint returns public events only.

## Tests

The core engine has no third-party dependency, so its test suite runs even before the API packages are installed:

```bash
python3 -m unittest discover -v
```

