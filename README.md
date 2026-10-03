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
The Persian game dashboard is available at `http://127.0.0.1:8000/ui/` (the root URL redirects there).

## Browser AI match

The browser experience is a cinematic, slide-by-slide match with one human (`P1`) and six independent AI agents. The player first chooses one of seven character portraits, privately receives a random role, selects a public role claim, and then moves through individual discussion, voting, role-specific night, and morning-news slides. Human and AI turns share the same filtered observation contract. The journal shows visible events and the human's own role information, claims, and role-specific private knowledge without leaking another player's hidden state.

Role claims are deliberately limited to `CITIZEN`, `DOCTOR`, or `DETECTIVE` for every human and AI player, regardless of the player's true role.

Interactive matches use `gpt-5.6-luna` for all six AI players when `OPENAI_API_KEY` is configured. Each player remains a separate `AIAgent` with its own memory, beliefs, and hypotheses. If the key is unavailable, the server keeps the match playable with deterministic fallback agents. Configure the player model independently from the optional analyst:

```dotenv
OPENAI_PLAYER_MODEL=gpt-5.6-luna
```

The interface supports Persian, English, and German. The selected language is also passed to each AI agent so public dialogue follows the player's language.

The browser follows public events over Server-Sent Events (SSE), which fits the one-way server-to-spectator flow and reconnects automatically:

```text
POST /games/ai
POST /games/interactive
POST /game/{game_id}/interactive/action
GET  /game/{game_id}/player/{player_id}/observation
GET  /game/{game_id}/run-state
POST /game/{game_id}/run/cancel
GET  /game/{game_id}/stream
```

The SSE stream contains public game events and sanitized run progress only. The interactive creation response returns only the human player's token; other player tokens, private investigation results, hidden roles, model prompts, and API keys are never included.

Public run progress excludes participant actions, role-specific waiting actions, and detailed failure transcripts. Public viewers see `RUNNING` while a human is deciding; the human's authenticated `GET /game/{game_id}/run-state` (with `X-Player-Token`) returns `WAITING_FOR_HUMAN`. Legal actions remain available through the authenticated observation endpoint.

Cancel an interactive match with its human's `X-Player-Token`. For an AI-only match, creation returns a one-time `control_token`; send it as `X-Run-Token` to cancel. Public progress and SSE never include this credential. Managed matches reject the generic player action endpoint; interactive participants must use `/interactive/action` so the runner and engine advance together.

HTTP game creation rejects client-provided `seed` values. Role assignment uses server-owned system randomness. Explicit seeds remain supported only by the in-process engine for tests and offline simulations.

The browser saves the active match credentials and narrative position in local storage on the same browser profile. Refreshing or reopening the page resumes the existing match, including an unread final vote/night result. Returning home ends the active match and clears the saved session. Game state is still in server memory: a server restart expires the match, and the browser displays an explanation instead of waiting indefinitely.

## API flow

Create a game:

```http
POST /games
Content-Type: application/json

{
  "player_types": ["HUMAN", "AI", "AI", "HUMAN", "AI", "AI", "HUMAN"]
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

Run the frontend regression suite (Node.js, no package installation needed):

```bash
node --test tests/frontend.test.cjs
```

For manual offline verification with a 1.5-second action-response delay:

```bash
PYTHONPATH=. .venv/bin/python audit/2026-10-02/serve_delayed.py
```

Open `http://127.0.0.1:8017/ui/`. This test server uses offline agents and makes no remote model requests.

## Cloudflare Workers deployment

The repository includes a Python Worker entrypoint in `worker.py` and a
`wrangler.jsonc` configuration. Cloudflare serves the `Frontend/` directory as
Workers Static Assets while the FastAPI routes handle the API first. The
entrypoint also translates the existing `/ui/...` browser paths to the asset
root, so CSS, JavaScript, images, fonts, and audio do not return 404 errors.

Install the Cloudflare Python Worker tooling and run the Worker locally:

```bash
uv sync --dev
uv run pywrangler dev
```

After authenticating Wrangler, deploy it with:

```bash
npx wrangler login
uv run pywrangler deploy
```

Configure the AI provider values as Cloudflare secrets rather than committing
`.env` files. The exact secret names are the environment variable names used
by `app/ai/config.py`, for example:

```bash
npx wrangler secret put OPENAI_API_KEY
```

The current game repository is in-memory, so a Worker restart or isolate change
can expire active matches. Persistent multiplayer state should be moved to a
Cloudflare Durable Object or another Cloudflare storage binding before treating
the deployment as production-ready.
