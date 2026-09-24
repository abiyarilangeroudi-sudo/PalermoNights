from __future__ import annotations

from threading import RLock

from .domain import Game, RuleViolation


class InMemoryGameRepository:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}
        self.lock = RLock()

    def add(self, game: Game) -> None:
        with self.lock:
            self._games[game.game_id] = game

    def get(self, game_id: str) -> Game:
        with self.lock:
            try:
                return self._games[game_id]
            except KeyError as exc:
                raise RuleViolation("GAME_NOT_FOUND") from exc

