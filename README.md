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

Python 3.13+ is required.

```bash
python3 -m venv .venv
.venv/bin/pip install -e . 'pytest>=8,<9'
.venv/bin/python -m app
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.
The Persian game dashboard is available at `http://127.0.0.1:8000/ui/` (the root URL redirects there).

## Browser AI match

The browser experience is a cinematic, slide-by-slide match with one human (`P1`) and six independent AI agents. The player first chooses one of seven character portraits, privately receives a random role, selects a public role claim, and then moves through individual discussion, voting, role-specific night, and morning-news slides. Human and AI turns share the same filtered observation contract. The journal shows visible events and the human's own role information, claims, and role-specific private knowledge without leaking another player's hidden state.

Role claims are deliberately limited to `CITIZEN`, `DOCTOR`, or `DETECTIVE` for every human and AI player, regardless of the player's true role.

Interactive matches use the human participant's own OpenAI API key for all six AI players. Each player remains a separate `AIAgent` with its own memory, beliefs, and hypotheses. The deployment's `OPENAI_API_KEY` is never used for an interactive match. Configure the player model independently from the optional analyst:

```dotenv
OPENAI_PLAYER_MODEL=gpt-5.6-luna
```

The interface supports Persian, English, and German. The selected language is also passed to each AI agent so public dialogue follows the player's language.

The browser follows public events over Server-Sent Events (SSE), which fits the one-way server-to-spectator flow and reconnects automatically:

```text
POST /games/ai
POST /games/interactive
POST /game/{game_id}/interactive/continue
POST /game/{game_id}/interactive/action
GET  /game/{game_id}/player/{player_id}/observation
GET  /game/{game_id}/run-state
POST /game/{game_id}/run/cancel
GET  /game/{game_id}/stream
```

The SSE stream contains public game events and sanitized run progress only. The interactive creation response returns only the human player's token; other player tokens, private investigation results, hidden roles, model prompts, and API keys are never included. The browser submits its OpenAI key only to `/interactive/continue`, one AI turn at a time. The key is held in tab memory, is never written to local storage, snapshots, audits, or logs, and must be entered again after a reload. Participant-funded games are not executed by background alarms, so a server restart cannot silently switch them to the deployment owner's key.

Public run progress excludes participant actions, role-specific waiting actions, and detailed failure transcripts. Public viewers see `RUNNING` while a human is deciding; the human's authenticated `GET /game/{game_id}/run-state` (with `X-Player-Token`) returns `WAITING_FOR_HUMAN`. Legal actions remain available through the authenticated observation endpoint.

Cancel an interactive match with its human's `X-Player-Token`. For an AI-only match, creation returns a one-time `control_token`; send it as `X-Run-Token` to cancel. Public progress and SSE never include this credential. Managed matches reject the generic player action endpoint; interactive participants must use `/interactive/action` so the runner and engine advance together.

HTTP game creation rejects client-provided `seed` values. Role assignment uses server-owned system randomness. Explicit seeds remain supported only by the in-process engine for tests and offline simulations.

The browser saves the active match token and narrative position in local storage on the same browser profile, but never the OpenAI API key. Refreshing or reopening the page resumes the existing match and asks for the key again only when another AI turn is needed. Returning home preserves the active match and exposes Resume and End game controls; ending it requires confirmation and a successful server response. Speech/answer drafts and vote selections survive refresh. The Python server checkpoints game state, agent memory, budgets, and action receipts in SQLite and recovers them after restart. Games created before durable storage was installed cannot be recovered from their old in-memory server after it exits.

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

## Evidence and public vote positions

Agents receive a filtered dossier of public claims, votes, reveals and linked
questions/answers, plus an optional bounded strategy library. An exhaustive
assessment is not required and the server does not substitute a prior public
position for a legal vote. Changes of opinion, bluffing and imperfect judgments
remain part of play.

Optional public positions from older records remain readable in the journal.
References attached to public events must identify actual public events; private
investigations are not valid public citations. Technical event IDs and role enums
are localized in dialogue. Repeated observations do not repeatedly drift beliefs.

Offline tests verify contracts and privacy, not the quality of live model strategy
or naturalness of dialogue. Evaluate those separately with recorded, budgeted live
matches, using the postgame analysis and reviewed resource cards.

## Durable hosting and public play limits

Run one Python application worker on a durable local volume. `PALERMO_DB_PATH`
defaults to `.palermo-data/games.sqlite3`; this private directory is Git-ignored.
A process lock rejects a second writer, so do not use `uvicorn --workers 2` or
share the database across hosts. Shutdown checkpoints active runs as resumable;
startup restores the same game, tokens, transcript, agent memories, and counters.
Do not delete the database or its WAL while the server is running. Back up with
SQLite's backup API, or stop the server and copy the entire data directory.

Set a long random `PALERMO_PLAY_KEY` in the server environment/`.env` for public
online play and serve over HTTPS. The UI asks for this **play access code**, never
the model API key. `POST /session` exchanges `X-Play-Key` for a signed, HttpOnly,
SameSite=Strict cookie valid for one hour (Secure over HTTPS). Requests for live
games without a valid session return 401 before allocating a runner. Changing the
play key invalidates existing access sessions; participant tokens remain valid.
For direct loopback development only, `PALERMO_ALLOW_LOCAL_LIVE=1` opts out of this
access prompt. Do not use that option behind a public reverse proxy. Configure
uvicorn's trusted proxy addresses explicitly; arbitrary `X-Forwarded-For` headers
are not treated as a client identity by the application.

Default creation limits, configurable via `.env.example`:

| Limit | Default |
| --- | ---: |
| Active games across the server | 8 |
| Active games per client IP | 2 |
| Active live games | 2 |
| Creation attempts per client per hour | 10 |
| Creation attempts across the server per hour | 100 |
| Live creation attempts per rolling 24 hours | 20 |
| Model decisions per AI player per game | 20 |
| Optional target-gate decisions per AI player per game | 20 |
| Game lifetime, including time waiting for a human | 24 hours |

Admission history survives restart. Failed configuration/start attempts consume
an admission slot conservatively. At the per-player decision ceiling, validated
deterministic fallback continues the match. HTTP `live_action_budget=0` now means
the bounded server default, not unlimited. Each model generation is capped at the
lower of its configured value and 4096 output tokens; a primary provider has at
most three HTTP attempts. Cross-provider failover is disabled in `build_runner`
to keep that bound explicit. A model decision has at most a 60-second deadline,
the optional gate at most 30 seconds, and each autonomous run segment 15 minutes.
These are request/token ceilings, not a currency-denominated billing cap. Model
work already accepted by a provider may still be billed after cancellation.

Accepted interactive actions and their `request_id` receipts commit in the same
SQLite transaction. A retry with the same ID and payload returns the original
response; changing the payload under the same ID returns 409. Optional
`expected_event_id` rejects stale actions. Diagnostic audit-log failure is
nonfatal; failure to save authoritative state rolls back a human action.

Browser requests include a 15-second deadline covering both headers and body.
Connection recovery uses a 1–15-second backoff, retains drafts, and reconciles
accepted action IDs before offering a retry. Local storage contains the
match-scoped participant token, so use a trusted browser profile on shared
devices. It does not contain the OpenAI API key.

## Real-browser regression tests

```bash
npm ci
npx playwright install chromium
npm test
npm run test:browser
```

The browser suite starts an isolated local Python server with a temporary SQLite
database. It uses offline agents and makes no model calls. Set `PALERMO_PYTHON`
if Python is not at `.venv/bin/python`, `PALERMO_TEST_PORT` if port 8034 is occupied,
or `PALERMO_BROWSER_EXECUTABLE` to use an installed Chromium/Chrome executable.
It covers voting overlays, narrow-screen long answers, mention/draft persistence,
home/resume, stalled responses, a complete offline game, and a lost accepted-action
response. `.github/workflows/tests.yml` runs Python, controller, and browser tests.

For a negative control that reproduces the original voting defect:

```bash
PALERMO_REPRO_OLD_CSS=1 node --test --test-name-pattern='voting picker' tests/browser/reliability.test.cjs
```

That command should fail: the player card intercepts the option click. The normal
suite should pass.

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

The Worker stores versioned snapshots, action receipts, provider-budget reservations,
admissions, audits and lesson candidates in Durable Object SQL. Bounded alarm turns
resume queued games after eviction without depending on a detached asyncio task.
The existing named object is retained; this release does not migrate games to new IDs.
Game state that an older deployment never persisted cannot be recovered by this release.

`python3 scripts/package_worker.py` stages only application sources. Pywrangler
vendors runtime dependencies; `.env`, the local virtual environments, tests and
local game databases must never be bundled. `/health` exposes a release label,
deployment ID and storage type for comparing a deployed backend with its assets.

Set `PALERMO_PLAY_KEY` as a Worker secret to enable authenticated live play;
`OPENAI_API_KEY` and `OPENAI_PLAYER_MODEL` configure the provider. Never put secret
values in Git. Optional `PALERMO_REVIEW_KEY` is a separate editor credential.
After deployment, verify `/health`, create an offline match, wait for completion,
and confirm `/game/{id}/analysis` before a paid model test.

## Voting and postgame learning

Only `vote_target` is required. Citizens may supply `suspect_2` and/or
`trusted_player`, each a distinct living player other than themselves. Mafia
submits only a vote; legacy auxiliary fields are ignored. Citizen trust snapshots
are published as subjective wills on elimination or with the morning kill result.
Temporary shunning does not publish a will.

Agents receive a bounded, optional reference library, including strategy tradeoffs
and counterexamples. Legal model votes and changes of opinion are not overridden.
Completed matches persist factual analysis and **candidate** lessons. These are
not automatically injected into future games or treated as proof of a strategy.
The postgame UI downloads the analysis; a human editor can approve a concise card:

- Locally, stop the server and run `python -m app.lesson_review --database PATH
  --game-id ID --card reviewed-card.json` (write this command on one line).
- On the Worker, POST a JSON card to `/game/{id}/analysis/review` with the separate
  `X-Review-Key` header. Cards require `title`, `observation`, `hypothesis`,
  `counterexample`, and `limitations`. Do not include secrets or live-match details.

Only reviewed cards from completed games enter the bounded reference context.
This enriches the agents' resources; it does not retrain model weights.

Browser regressions run in Chromium and WebKit (including narrow portrait and
landscape viewports). WebKit testing is not a claim of testing physical iPhones.
