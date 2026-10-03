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
