import pytest


@pytest.fixture(autouse=True)
def no_embedding_service(monkeypatch):
    """A test never reaches Voyage AI, even on a machine where the key is set."""
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
