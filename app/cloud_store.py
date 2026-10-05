"""Synchronous Durable Object SQL adapter; no local filesystem or sqlite3."""
import json


class CloudStore:
    def __init__(self, sql):
        self.sql = sql
        sql.exec('CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        sql.exec('CREATE TABLE IF NOT EXISTS admissions (owner TEXT, live INTEGER, time REAL)')
        sql.exec('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, game_id TEXT, body TEXT)')
        sql.exec('CREATE TABLE IF NOT EXISTS lessons (id TEXT PRIMARY KEY, body TEXT NOT NULL)')

    def rows(self, statement, *args):
        cursor = self.sql.exec(statement, *args)
        # raw() yields JS arrays in Workers and ordinary rows in the test adapter.
        return [list(row) for row in cursor.raw()]

    def save(self, value):
        self.sql.exec('INSERT OR REPLACE INTO snapshots VALUES (?, ?)', value['game']['game_id'], json.dumps(value, ensure_ascii=False))

    def all(self):
        values = [json.loads(row[0]) for row in self.rows('SELECT body FROM snapshots')]
        if any(v.get('version') != 1 for v in values):
            raise RuntimeError('Unsupported game snapshot version')
        return values

    def admissions_since(self, since):
        return self.rows('SELECT owner, live, time FROM admissions WHERE time > ?', since)

    def record_admission(self, record):
        self.sql.exec('DELETE FROM admissions WHERE time < ?', record[2] - 86400)
        self.sql.exec('INSERT INTO admissions VALUES (?, ?, ?)', *record)

    def audit(self, game_id, record):
        self.sql.exec('INSERT INTO audit(game_id, body) VALUES (?, ?)', game_id, json.dumps(record, ensure_ascii=False))
        self.sql.exec('DELETE FROM audit WHERE game_id = ? AND id NOT IN (SELECT id FROM audit WHERE game_id = ? ORDER BY id DESC LIMIT 1000)', game_id, game_id)

    def save_lesson(self, value):
        self.sql.exec('INSERT OR IGNORE INTO lessons VALUES (?, ?)', value['game_id'], json.dumps(value, ensure_ascii=False))

    def update_lesson(self, value):
        self.sql.exec("INSERT OR REPLACE INTO lessons VALUES (?, ?)", value["game_id"], json.dumps(value, ensure_ascii=False))

    def lessons(self):
        return [json.loads(row[0]) for row in self.rows('SELECT body FROM lessons ORDER BY id DESC')]
