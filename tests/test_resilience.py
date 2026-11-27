"""Section 10: retry, circuit breaker and a degraded message instead of a crash."""

import anthropic
import pytest

from escale import assistant, llm
from escale.agent import AgentResult, run_agent
from escale.resilience import DEGRADED_MESSAGE, CircuitBreaker, CircuitOpenError
from escale.toolbox import Toolbox
from tests.fakes import FakeClient, api_error, response, text


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def outage():
    raise api_error(anthropic.InternalServerError, 500)


def test_the_breaker_opens_after_the_threshold():
    breaker = CircuitBreaker(threshold=3, clock=Clock())

    for _ in range(3):
        with pytest.raises(anthropic.InternalServerError):
            breaker.call(outage)

    assert breaker.is_open
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "jamais appelé")


def test_an_open_breaker_does_not_call_the_service():
    calls = []
    breaker = CircuitBreaker(threshold=1, clock=Clock())
    with pytest.raises(anthropic.InternalServerError):
        breaker.call(outage)

    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: calls.append("appel"))

    assert calls == []


def test_after_the_cooldown_one_call_is_let_through_and_a_success_closes_it():
    clock = Clock()
    breaker = CircuitBreaker(threshold=1, cooldown=30, clock=clock)
    with pytest.raises(anthropic.InternalServerError):
        breaker.call(outage)

    clock.now = 31

    assert breaker.call(lambda: "revenu") == "revenu"
    assert not breaker.is_open
    assert breaker.failures == 0


def test_a_failure_after_the_cooldown_opens_it_again():
    clock = Clock()
    breaker = CircuitBreaker(threshold=1, cooldown=30, clock=clock)
    with pytest.raises(anthropic.InternalServerError):
        breaker.call(outage)
    clock.now = 31

    with pytest.raises(anthropic.InternalServerError):
        breaker.call(outage)

    assert breaker.is_open


def test_a_success_resets_the_count_of_failures():
    breaker = CircuitBreaker(threshold=2, clock=Clock())
    with pytest.raises(anthropic.InternalServerError):
        breaker.call(outage)

    breaker.call(lambda: "ok")
    with pytest.raises(anthropic.InternalServerError):
        breaker.call(outage)

    assert not breaker.is_open


def test_a_bad_request_is_our_bug_not_an_outage_and_never_opens_the_breaker():
    breaker = CircuitBreaker(threshold=1, clock=Clock())

    def bad_request():
        raise api_error(anthropic.BadRequestError, 400)

    for _ in range(3):
        with pytest.raises(anthropic.BadRequestError):
            breaker.call(bad_request)

    assert not breaker.is_open


def test_the_agent_answers_with_a_degraded_message_when_the_api_stays_down(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    client = FakeClient(*[api_error(anthropic.InternalServerError, 500)] * 5)

    result = run_agent(client, [{"role": "user", "content": "q"}], Toolbox([]), system="s")

    assert result.stop_reason == "unavailable"
    assert result.text == DEGRADED_MESSAGE
    assert not result.is_complete


def test_the_agent_does_not_even_try_when_the_breaker_is_open(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    breaker = CircuitBreaker(threshold=1, clock=Clock())
    down = FakeClient(*[api_error(anthropic.InternalServerError, 500)] * 5)
    messages = [{"role": "user", "content": "q"}]
    run_agent(down, messages, Toolbox([]), system="s", breaker=breaker)

    healthy = FakeClient(response(text("ok")))
    result = run_agent(healthy, messages, Toolbox([]), system="s", breaker=breaker)

    assert result.stop_reason == "unavailable"
    assert healthy.requests == []


def test_a_bad_request_still_raises_in_the_agent():
    client = FakeClient(api_error(anthropic.BadRequestError, 400))

    with pytest.raises(anthropic.BadRequestError):
        run_agent(client, [{"role": "user", "content": "q"}], Toolbox([]), system="s")


def test_the_degraded_message_is_shown_to_the_user():
    result = AgentResult(DEGRADED_MESSAGE, "unavailable", 1)

    assert assistant.describe(result) == DEGRADED_MESSAGE


def test_ask_retries_a_transient_error_before_giving_up(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    client = FakeClient(api_error(anthropic.RateLimitError, 429), response(text("ok")))

    assert llm.ask(client, "q") == "ok"
