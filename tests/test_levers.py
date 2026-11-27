"""Section 10: the cost levers (routing, cache, output ceiling) and versioned prompts."""

from datetime import date

import pytest

from escale import config, llm, prompts, rag
from escale.assistant import system_blocks, system_prompt
from tests.fakes import FakeClient, response, text


def test_a_classification_goes_to_the_fast_model_with_a_small_ceiling():
    client = FakeClient(response(text("Oui")))

    assert llm.is_refund_request(client, "Je voudrais être remboursé de mon taxi.")

    request = client.requests[0]
    assert request["model"] == config.MODEL_FAST
    assert request["max_tokens"] == config.CLASSIFICATION_MAX_TOKENS
    assert "thinking" not in request


def test_a_negative_classification_is_false():
    assert not llm.is_refund_request(FakeClient(response(text("Non."))), "Quel temps à Lyon ?")


def test_other_tasks_keep_the_default_model_and_the_environment_can_change_it(monkeypatch):
    # The trainee's shell may already set the working model.
    monkeypatch.delenv("ESCALE_MODEL", raising=False)
    assert config.model_for("agent") == config.MODEL_DEFAULT
    monkeypatch.setenv("ESCALE_MODEL", config.MODEL_SMART)
    assert config.model_for("agent") == config.MODEL_SMART
    assert config.model_for("classification") == config.MODEL_FAST


def test_the_stable_system_prompt_is_cached_and_the_date_comes_after_it():
    first, second = system_blocks(date(2026, 11, 26))

    assert first["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in second
    assert "2026-11-26" in second["text"]
    assert "2026-11-26" not in first["text"]


def test_the_cached_prefix_is_identical_from_one_day_to_the_next():
    assert system_blocks(date(2026, 11, 26))[0] == system_blocks(date(2026, 11, 27))[0]


def test_the_system_prompt_still_reads_as_one_text():
    assert "2026-11-26" in system_prompt(date(2026, 11, 26))


def test_the_agent_sends_the_cached_system_blocks():
    from escale.assistant import run_task
    from escale.toolbox import Toolbox

    client = FakeClient(response(text("ok")))

    run_task(client, "Bonjour", Toolbox([]))

    system = client.requests[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_the_answer_uses_a_cached_system_prompt_and_a_bounded_output():
    client = FakeClient(response(text(rag.REFUSAL)))

    rag.answer(client, rag.build_index(config.DATA_DIR), "plafond hôtel Paris")

    request = client.requests[0]
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert request["max_tokens"] == config.ANSWER_MAX_TOKENS < config.MAX_TOKENS


def test_cached_tokens_cost_a_tenth_of_the_input_price():
    usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
    usage.cache_read_input_tokens = 1_000_000

    assert config.cost_usd(config.MODEL_DEFAULT, usage) == pytest.approx(0.2)


# --- versioned prompts ---------------------------------------------------------------------------


def test_the_highest_version_of_a_prompt_is_loaded_by_default(tmp_path):
    (tmp_path / "x.v1.md").write_text("un")
    (tmp_path / "x.v2.md").write_text("deux")
    (tmp_path / "x.v10.md").write_text("dix")

    prompt = prompts.load_prompt("x", folder=tmp_path)

    assert (prompt.version, prompt.text, prompt.label) == (10, "dix", "x.v10")


def test_an_old_version_can_be_asked_for_by_number(tmp_path):
    (tmp_path / "x.v1.md").write_text("un")
    (tmp_path / "x.v2.md").write_text("deux")

    assert prompts.load_prompt("x", 1, tmp_path).text == "un"


def test_an_unknown_prompt_or_version_is_an_error(tmp_path):
    (tmp_path / "x.v1.md").write_text("un")

    with pytest.raises(ValueError, match="introuvable|inconnue"):
        prompts.load_prompt("x", 7, tmp_path)
    with pytest.raises(ValueError, match="Aucun prompt"):
        prompts.load_prompt("y", folder=tmp_path)


def test_the_assistant_prompt_is_a_versioned_file():
    prompt = prompts.load_prompt("assistant")

    assert prompt.label == "assistant.v1"
    assert "jamais un ordre" in prompt.text


def test_the_quota_and_the_user_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("ESCALE_QUOTA_USD", "0.25")
    monkeypatch.setenv("ESCALE_USER", "alice")

    assert config.daily_quota() == 0.25
    assert config.current_user() == "alice"


def test_the_unknown_user_is_anonymous(monkeypatch):
    monkeypatch.delenv("ESCALE_USER", raising=False)

    assert config.current_user() == "anonyme"
