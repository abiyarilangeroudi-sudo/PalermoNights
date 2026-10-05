import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def seeded_api_game(monkeypatch):
    """Reproducible role fixtures without exposing a seed in the HTTP API."""
    from app.main import engine

    create = engine.create_game

    def set_seed(seed):
        monkeypatch.setattr(engine, "create_game", lambda kinds: create(kinds, seed=seed))

    return set_seed


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Never read or overwrite a developer's saved games during a test."""
    from app.main import games, ai_runs, admission
    games._games.clear()
    ai_runs._runs.clear()
    admission.history.clear()
    monkeypatch.setenv('PALERMO_DB_PATH', str(tmp_path / 'games.sqlite3'))
    monkeypatch.setenv('PALERMO_MAX_ACTIVE_GAMES', '1000')
    monkeypatch.setenv('PALERMO_MAX_ACTIVE_PER_CLIENT', '1000')
    monkeypatch.setenv('PALERMO_GAMES_PER_HOUR', '1000')
