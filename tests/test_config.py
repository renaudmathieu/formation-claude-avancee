from types import SimpleNamespace

import pytest

from escale import config
from escale.llm import send
from tests.fakes import FakeClient, response, text


def test_cost_of_a_plain_call():
    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=1_000_000)

    assert config.cost_usd(config.MODEL_DEFAULT, usage) == pytest.approx(12.0)
    assert config.cost_usd(config.MODEL_FAST, usage) == pytest.approx(0.60)


def test_cache_tokens_use_their_own_factors():
    usage = SimpleNamespace(
        input_tokens=0,
        output_tokens=0,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )

    # Sonnet input is 2 USD: read = 0.2, write = 2.5.
    assert config.cost_usd(config.MODEL_DEFAULT, usage) == pytest.approx(2.7)


def test_unknown_model_is_an_error_not_a_free_call():
    with pytest.raises(ValueError):
        config.cost_usd("claude-inconnu", SimpleNamespace(input_tokens=1, output_tokens=1))


def test_every_model_has_a_price():
    for model in (config.MODEL_FAST, config.MODEL_DEFAULT, config.MODEL_SMART, config.MODEL_TOP):
        assert model in config.PRICES


def test_send_uses_the_model_and_ceiling_from_config(monkeypatch):
    monkeypatch.delenv("ESCALE_MODEL", raising=False)
    client = FakeClient(response(text("ok")))

    send(client, [{"role": "user", "content": "Bonjour"}])

    assert client.requests[0]["model"] == config.MODEL_DEFAULT
    assert client.requests[0]["max_tokens"] == config.MAX_TOKENS


def test_env_var_overrides_the_default_model(monkeypatch):
    monkeypatch.setenv("ESCALE_MODEL", config.MODEL_FAST)

    assert config.default_model() == config.MODEL_FAST


def test_verifier_reports_a_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config.verifier()
