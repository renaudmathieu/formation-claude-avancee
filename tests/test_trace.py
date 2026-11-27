"""Section 10: one JSON line per call, cost per question, quota, and no secret in the log."""

import json
from datetime import date
from types import SimpleNamespace

import anthropic
import pytest

from escale import llm
from escale.agent import run_agent
from escale.quota import Quota, QuotaExceededError
from escale.toolbox import Toolbox
from escale.trace import TracedClient, cost_per_question, mask_secrets, read_records
from scripts import cout_par_question
from tests.fakes import FakeClient, api_error, response, text, tool_use


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def trace_path(tmp_path):
    return tmp_path / "trace.jsonl"


def traced(fake, trace_path, **kwargs):
    return TracedClient(
        fake, path=trace_path, user="alice", prompt_version="assistant.v1", **kwargs
    )


def test_each_call_is_one_json_line_with_what_is_needed_to_read_the_cost(trace_path):
    fake = FakeClient(response(text("Bonjour"), input_tokens=1000, output_tokens=200))

    llm.ask(traced(fake, trace_path), "Salut")

    (line,) = lines(trace_path)
    assert line["user"] == "alice"
    assert line["prompt_version"] == "assistant.v1"
    assert line["model"] == "claude-sonnet-5-5"
    assert (line["input_tokens"], line["output_tokens"]) == (1000, 200)
    assert line["cost_usd"] == pytest.approx(0.004)
    assert line["status"] == "ok"
    assert {"time", "duration_ms", "question_id", "cache_read_tokens"} <= line.keys()


def test_cache_tokens_are_logged_and_billed_at_their_own_price(trace_path):
    reply = response(text("ok"), input_tokens=0, output_tokens=0)
    reply.usage.cache_read_input_tokens = 1_000_000
    reply.usage.cache_creation_input_tokens = 1_000_000

    llm.ask(traced(FakeClient(reply), trace_path), "Salut")

    (line,) = lines(trace_path)
    assert (line["cache_read_tokens"], line["cache_write_tokens"]) == (1_000_000, 1_000_000)
    assert line["cost_usd"] == pytest.approx(0.2 + 2.5)


def test_a_failed_call_is_logged_and_the_error_still_reaches_the_caller(trace_path):
    fake = FakeClient(api_error(anthropic.BadRequestError, 400))

    with pytest.raises(anthropic.BadRequestError):
        llm.ask(traced(fake, trace_path), "Salut")

    (line,) = lines(trace_path)
    assert line["status"] == "error"
    assert line["error"].startswith("BadRequestError")


def test_a_stream_is_logged_once_it_is_finished(trace_path):
    fake = FakeClient(response(text("Bonjour"), input_tokens=10, output_tokens=5))

    fragments = list(llm.stream(traced(fake, trace_path), [{"role": "user", "content": "Salut"}]))

    assert fragments == ["Bonjour"]
    (line,) = lines(trace_path)
    assert line["output_tokens"] == 5


def test_an_unwritable_log_does_not_stop_the_call(tmp_path, capsys):
    blocked = tmp_path / "fichier"
    blocked.write_text("je suis un fichier, pas un dossier")

    answer = llm.ask(traced(FakeClient(response(text("ok"))), blocked / "trace.jsonl"), "Salut")

    assert answer == "ok"
    assert "Écriture impossible" in capsys.readouterr().out


# --- cost per question ------------------------------------------------------------------------


def test_calls_of_one_question_are_added_up(trace_path):
    fake = FakeClient(
        response(tool_use("t", {}), stop_reason="tool_use", output_tokens=100),
        response(text("fin"), output_tokens=100),
        response(text("autre"), output_tokens=100),
    )
    client = traced(fake, trace_path)

    run_agent(client, [{"role": "user", "content": "q1"}], Toolbox([]), system="s")
    first = client.question_id
    client.new_question()
    llm.ask(client, "q2")

    questions = cost_per_question(read_records(trace_path))
    assert questions[first]["calls"] == 2
    assert questions[client.question_id]["calls"] == 1
    assert questions[first]["cost_usd"] > questions[client.question_id]["cost_usd"]


def test_the_report_lists_questions_by_cost_and_a_total(trace_path):
    client = traced(FakeClient(response(text("a"), output_tokens=100_000)), trace_path)
    llm.ask(client, "q")

    report = cout_par_question.report(read_records(trace_path))

    assert client.question_id in report
    assert "1.0" in report
    assert "assistant.v1" in report
    assert "total" in report


# --- no secret in a log ---------------------------------------------------------------------------


def test_the_api_key_never_appears_in_a_log_line(trace_path, monkeypatch):
    key = "sk-ant-api03-SECRETSECRETSECRET"
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    fake = FakeClient(api_error(anthropic.AuthenticationError, 401, f"invalid x-api-key {key}"))
    client = traced(fake, trace_path)

    with pytest.raises(anthropic.AuthenticationError):
        llm.ask(client, f"ma clé est {key}")

    assert key not in trace_path.read_text(encoding="utf-8")


def test_masking_hides_key_shapes_and_the_keys_of_the_environment(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "clé-bizarre-1234")

    masked = mask_secrets("a sk-ant-api03-abcdef123456 b pa-abcdefghij c clé-bizarre-1234")

    assert "abcdef" not in masked
    assert "bizarre" not in masked
    assert masked.count("[clé masquée]") == 3


def test_the_log_holds_no_prompt_and_no_answer(trace_path):
    llm.ask(
        traced(FakeClient(response(text("réponse confidentielle"))), trace_path), "question privée"
    )

    content = trace_path.read_text(encoding="utf-8")
    assert "confidentielle" not in content
    assert "privée" not in content


# --- the quota -------------------------------------------------------------------------------------


def line(user, cost, day="2026-11-26"):
    return json.dumps({"user": user, "cost_usd": cost, "time": f"{day}T09:00:00+00:00"}) + "\n"


def test_spent_today_counts_only_the_user_and_the_day(trace_path):
    trace_path.write_text(line("alice", 0.4) + line("bob", 5) + line("alice", 9, "2026-11-25"))

    quota = Quota(trace_path, 1.0, today=lambda: date(2026, 11, 26))

    assert quota.spent_today("alice") == pytest.approx(0.4)


def test_a_user_over_the_quota_is_refused_before_the_call(trace_path):
    trace_path.write_text(line("alice", 1.2))
    fake = FakeClient(response(text("jamais appelé")))
    quota = Quota(trace_path, 1.0, today=lambda: date(2026, 11, 26))

    with pytest.raises(QuotaExceededError, match="alice"):
        llm.ask(traced(fake, trace_path, quota=quota), "Salut")

    assert fake.requests == []


def test_the_quota_is_exceeded_by_the_calls_themselves(trace_path):
    quota = Quota(trace_path, 1.0)
    client = traced(
        FakeClient(
            response(text("a"), output_tokens=100_000), response(text("b"), output_tokens=100_000)
        ),
        trace_path,
        quota=quota,
    )

    llm.ask(client, "première")  # 1 USD: the limit is reached
    with pytest.raises(QuotaExceededError):
        llm.ask(client, "seconde")


def test_the_agent_ends_with_a_message_when_the_quota_is_spent(trace_path):
    trace_path.write_text(line("alice", 2.0))
    quota = Quota(trace_path, 1.0, today=lambda: date(2026, 11, 26))
    client = traced(FakeClient(response(text("jamais"))), trace_path, quota=quota)

    result = run_agent(client, [{"role": "user", "content": "q"}], Toolbox([]), system="s")

    assert result.stop_reason == "quota_exceeded"
    assert "Quota" in result.text


def test_another_user_is_not_blocked(trace_path):
    trace_path.write_text(line("bob", 50))
    quota = Quota(trace_path, 1.0, today=lambda: date(2026, 11, 26))

    assert llm.ask(traced(FakeClient(response(text("ok"))), trace_path, quota=quota), "q") == "ok"


def test_a_torn_line_does_not_lock_the_user_out(trace_path):
    trace_path.write_text("{pas du json\n" + line("alice", 0.1))

    assert Quota(trace_path, 1.0, today=lambda: date(2026, 11, 26)).spent_today("alice") == 0.1


def test_the_traced_client_has_the_shape_of_the_sdk_client(trace_path):
    client = traced(FakeClient(), trace_path)

    assert isinstance(client.beta, SimpleNamespace)
    assert callable(client.beta.messages.create) and callable(client.beta.messages.stream)
