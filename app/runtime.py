"""Single-process game ownership with durable checkpoints and restart recovery."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import fields
from datetime import UTC, datetime

from .persistence import game_from_dict, snapshot
from .ai.agent import AgentMemory, AgentState
from .ai.runner import RunnerEntry
from .ai.service import AIRun, build_runner, execute_run, update_run_progress
from .ai.config import AISettings


class GameRuntime:
    def __init__(self, engine, games, runs):
        self.engine, self.games, self.runs = engine, games, runs
        self.store = None
        self.external_scheduler = False

    def save(self, game_id):
        if self.store is not None:
            run = self.runs.get(game_id) if self.runs.contains(game_id) else None
            self.store.save(snapshot(self.games.get(game_id), run))
            if self.games.get(game_id).phase.value == 'GAME_OVER':
                from .ai.library import analyze_game
                self.store.save_lesson(analyze_game(self.games.get(game_id)))

    def start(self, run, runner, *, schedule=True):
        self.attach(run, runner)
        try:
            self.save(run.game_id)
        except Exception:
            self.runs._runs.pop(run.game_id, None)
            self.games._games.pop(run.game_id, None)
            raise
        if schedule:
            self.schedule(run)

    def schedule(self, run):
        if run.credential_mode == 'participant':
            return
        if not self.external_scheduler:
            run.task = asyncio.create_task(execute_run(run, run.runner))

    def attach(self, run, runner):
        run.runner = runner
        run.checkpoint = lambda: self.save(run.game_id)
        def progress(entry):
            update_run_progress(run, entry, audit=entry.source != 'human')
            # Human actions commit their receipt and checkpoint together in the API.
            if entry.source != 'human':
                run.checkpoint()
        runner.on_entry = progress
        for agent in runner.agents.values():
            # Persist reservations BEFORE calling providers (also across restarts).
            agent.checkpoint = run.checkpoint

    def replace_runner(self, run, *, mode, settings=None, allow_fallback=True):
        """Swap providers while preserving only serializable game and agent state."""
        from .main import interactive_player_names
        previous = run.runner
        runner = build_runner(
            self.engine, self.games.get(run.game_id), mode=mode, settings=settings,
            live_action_budget=run.live_action_budget, language=run.language,
            player_names=interactive_player_names(run.character_id or 1),
            allow_fallback=allow_fallback,
        )
        if previous is not None:
            runner.transcript = copy.deepcopy(previous.transcript)
            for pid, agent in runner.agents.items():
                source = previous.agents[pid]
                agent.state = copy.deepcopy(source.state)
                agent.remote_decisions_used = source.remote_decisions_used
                agent.gate_decisions_used = source.gate_decisions_used
                agent.last_failure = source.last_failure
        self.attach(run, runner)
        return runner

    def restore(self, value):
        game = game_from_dict(value['game'])
        self.games.add(game)
        if value.get('run') is None:
            return
        run = AIRun(**value['run'])
        self.runs.add(run)
        settings = None
        if run.mode == 'live' and run.credential_mode != 'participant':
            try:
                settings = (AISettings.for_openai_players(player_count=6)
                            if run.human_player_id else AISettings.from_environment())
            except ValueError:
                run.status = 'FAILED'
                run.error = 'ConfigurationError'
        from .main import interactive_player_names
        runner = build_runner(self.engine, game, mode=run.mode if settings else 'offline',
            settings=settings, live_action_budget=run.live_action_budget,
            language=run.language, player_names=interactive_player_names(run.character_id or 1))
        runner.transcript = [RunnerEntry(**{**entry, "corrections": tuple(entry.get("corrections", ()))}) for entry in value.get('transcript', [])]
        for pid, data in value.get('agents', {}).items():
            agent = runner.agents[pid]
            state = dict(data['state'])
            state['memory'] = [AgentMemory(**m) for m in state['memory']]
            state['seen_event_ids'] = set(state['seen_event_ids'])
            agent.state = AgentState(**state)
            agent.remote_decisions_used = data['remote_used']
            agent.gate_decisions_used = data['gate_used']
            agent.last_failure = data['last_failure']
        self.attach(run, runner)
        from .admission import ACTIVE, limit
        if run.status in ACTIVE and (datetime.now(UTC) - datetime.fromisoformat(run.created_at)).total_seconds() >= limit('PALERMO_GAME_TTL_SECONDS', 86400):
            run.status = 'CANCELLED'
            run.awaiting_actions.clear()
            run.finished_at = datetime.now(UTC).isoformat()
            self.save(run.game_id)
        if run.status in {'RUNNING', 'QUEUED'} and run.credential_mode != 'participant':
            self.schedule(run)

    async def expire(self):
        from .admission import ACTIVE, limit
        now = datetime.now(UTC)
        for run in list(self.runs._runs.values()):
            if run.status not in ACTIVE or (now - datetime.fromisoformat(run.created_at)).total_seconds() < limit('PALERMO_GAME_TTL_SECONDS', 86400):
                continue
            if run.task and not run.task.done():
                run.task.cancel()
                await asyncio.gather(run.task, return_exceptions=True)
            run.status = 'CANCELLED'
            run.awaiting_actions.clear()
            run.finished_at = now.isoformat()
            self.save(run.game_id)

    async def maintain(self):
        while True:
            await self.expire()
            await asyncio.sleep(30)

    async def stop(self):
        tasks = []
        for run in list(self.runs._runs.values()):
            if run.task and not run.task.done():
                run.suspending = True
                run.task.cancel()
                tasks.append(run.task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for game_id in self.games._games:
            self.save(game_id)

    def rollback(self, run, value):
        """Restore the same game object, so streams never hold a stale reference."""
        original = self.games.get(run.game_id)
        restored = game_from_dict(value['game'])
        for f in fields(original):
            setattr(original, f.name, getattr(restored, f.name))
        for name, data in value['run'].items():
            setattr(run, name, data)
        run.runner.transcript = [RunnerEntry(**{**entry, "corrections": tuple(entry.get("corrections", ()))}) for entry in value['transcript']]
        for pid, data in value.get('agents', {}).items():
            agent = run.runner.agents[pid]
            state = dict(data['state'])
            state['memory'] = [AgentMemory(**m) for m in state['memory']]
            state['seen_event_ids'] = set(state['seen_event_ids'])
            agent.state = AgentState(**state)
            agent.remote_decisions_used = data['remote_used']
            agent.gate_decisions_used = data['gate_used']
            agent.last_failure = data['last_failure']
