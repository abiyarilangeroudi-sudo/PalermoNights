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

## AI agents

Remote agents live under `app/ai/` and only receive the filtered public view, their own private view, legal actions, and their visible event feed. They never receive a `Game` or `Player` object. The current provider pool supports:

- Gemini `generateContent` with JSON Schema output.
- Hetzner's OpenAI-compatible Qwen endpoint. Thinking is disabled for this route so the completion budget produces final JSON instead of reasoning-only output.
- OpenAI Responses with strict Structured Outputs for the optional analyst.
- TypeSafe Jev as an optional legal-target gate for votes and night actions. Jev never writes player-facing dialogue.

Agent memory, hypotheses, and Mafia probabilities are local agent state. Investigation results and public role reveals update those beliefs without changing engine-owned Trust.

Validate configuration without making network requests:

```bash
.venv/bin/python -m app.ai.smoke
```

Send one minimal, redacted smoke request per configured provider:

```bash
.venv/bin/python -m app.ai.smoke --live
```

Run a deterministic, offline seven-agent match:

```bash
.venv/bin/python -m app.simulate
```

Run a bounded integration match. By default each agent gets one remote model decision and one Jev gate decision; all later actions use the validated deterministic fallback so development runs have a predictable cost and duration:

```bash
.venv/bin/python -m app.simulate --live
```

Use `--live-action-budget 0` only when an intentionally unbounded, fully remote match is desired. Each decision has a separate hard deadline even when provider failover is configured.

Never expose `.env` or any provider key to a browser. `.env` is ignored by Git; `.env.example` contains only safe placeholders.

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

The complete suite, including async provider adapters and a full headless match, runs with:

```bash
.venv/bin/pytest
```
