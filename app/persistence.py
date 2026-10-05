"""Versioned JSON snapshots and a single-writer durable local store."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, fields
from pathlib import Path
from threading import RLock

from .domain import Game, Player, Event, Question, VoteDecision, Investigation, Role, Phase, Faction, PlayerType


def game_from_dict(data: dict) -> Game:
    data = dict(data)
    data['phase'] = Phase(data['phase'])
    data['winner'] = Faction(data['winner']) if data['winner'] else None
    players = {}
    for pid, raw in data['players'].items():
        raw = dict(raw)
        raw['role'] = Role(raw['role'])
        raw['player_type'] = PlayerType(raw['player_type'])
        raw['role_claim'] = Role(raw['role_claim']) if raw['role_claim'] else None
        raw['investigations'] = [Investigation(**{**i, 'result': Role(i['result'])}) for i in raw['investigations']]
        players[pid] = Player(**raw)
    data['players'] = players
    data['events'] = [Event(**e) for e in data['events']]
    data['questions'] = [Question(**q) for q in data['questions']]
    data['vote_decisions'] = {pid: VoteDecision(**v) for pid, v in data['vote_decisions'].items()}
    return Game(**data)


def snapshot(game: Game, run=None) -> dict:
    result = {'version': 1, 'game': asdict(game), 'run': None}
    if run is None:
        return result
    excluded = {'task', 'runner', 'checkpoint', 'suspending'}
    result['run'] = {f.name: getattr(run, f.name) for f in fields(run) if f.name not in excluded}
    if run.runner is None:
        return result
    result['transcript'] = [asdict(e) for e in run.runner.transcript]
    result['agents'] = {}
    for pid, agent in run.runner.agents.items():
        data = asdict(agent.state)
        data['seen_event_ids'] = sorted(data['seen_event_ids'])
        result['agents'][pid] = {
            'state': data, 'remote_used': agent.remote_decisions_used,
            'gate_used': agent.gate_decisions_used, 'last_failure': agent.last_failure,
        }
    return result


class SnapshotStore:
    def __init__(self, path: str):
        self.path = path
        self.connection = None
        self.owner = None
        self.lock = RLock()

    def open(self):
        if self.connection is not None:
            return
        if self.path != ':memory:':
            import fcntl
            path = Path(self.path)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.owner = open(str(path) + '.lock', 'a')
            try:
                fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                self.owner.close(); self.owner = None
                raise RuntimeError('Another server owns this database; use one application worker.') from exc
        import sqlite3
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.connection.execute('CREATE TABLE IF NOT EXISTS admissions (owner TEXT, live INTEGER, time REAL)')
        self.connection.execute('CREATE TABLE IF NOT EXISTS lessons (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.connection.commit()
        if self.path != ':memory:':
            os.chmod(self.path, 0o600)

    def save(self, value: dict):
        body = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        with self.lock, self.connection:
            self.connection.execute('INSERT OR REPLACE INTO snapshots VALUES (?, ?)', (value['game']['game_id'], body))

    def all(self):
        with self.lock:
            rows = [json.loads(row[0]) for row in self.connection.execute('SELECT body FROM snapshots')]
        if any(row.get('version') != 1 for row in rows):
            raise RuntimeError('Unsupported game snapshot version')
        return rows

    def admissions_since(self, since):
        with self.lock:
            return list(self.connection.execute('SELECT owner, live, time FROM admissions WHERE time > ?', (since,)))

    def record_admission(self, record):
        with self.lock, self.connection:
            self.connection.execute('DELETE FROM admissions WHERE time < ?', (record[2] - 86400,))
            self.connection.execute('INSERT INTO admissions VALUES (?, ?, ?)', record)

    def save_lesson(self, value):
        with self.lock, self.connection:
            self.connection.execute('INSERT OR IGNORE INTO lessons VALUES (?, ?)', (value['game_id'], json.dumps(value, ensure_ascii=False)))

    def update_lesson(self, value):
        with self.lock, self.connection:
            self.connection.execute("INSERT OR REPLACE INTO lessons VALUES (?, ?)", (value["game_id"], json.dumps(value, ensure_ascii=False)))

    def lessons(self):
        with self.lock:
            return [json.loads(row[0]) for row in self.connection.execute('SELECT body FROM lessons ORDER BY id DESC')]

    def close(self):
        if self.connection:
            self.connection.close(); self.connection = None
        if self.owner:
            self.owner.close(); self.owner = None
