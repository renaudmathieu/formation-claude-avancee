"""The agent loop: call Claude, run the tools it asks for, and start again."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from escale.config import DEFAULT_BUDGET_USD, cost_usd, default_model
from escale.llm import RETRYABLE, send, text_of, with_retry
from escale.quota import QuotaExceededError
from escale.resilience import DEGRADED_MESSAGE, CircuitBreaker, CircuitOpenError
from escale.toolbox import Toolbox

log = logging.getLogger("escale.agent")

MAX_ITERATIONS = 20
UNTRUSTED_TAG = "contenu_externe"
REFUSED_MESSAGE = "Action refusée par l'utilisateur : elle n'a pas été exécutée."

# A confirmation callback gets the tool name and its input, and answers yes or no.
Confirm = Callable[[str, dict], bool]


def refuse_all(name: str, tool_input: dict) -> bool:
    """Default confirmation: no. An irreversible action never runs without a human."""
    return False


@dataclass(frozen=True)
class AgentResult:
    """How a run ended. `stop_reason` is the API's, or `iteration_limit` / `budget_limit`
    for our own guards. `cost_usd` is what the run has spent."""

    text: str
    stop_reason: str
    iterations: int
    cost_usd: float = 0.0

    @property
    def is_complete(self) -> bool:
        return self.stop_reason == "end_turn"


def wrap_untrusted(source: str, content: str) -> str:
    """Put what a tool returned between tags, so that it reads as data and not as an order.

    The closing tag is broken inside the content: a document cannot end the block early.
    """
    safe = content.replace(f"</{UNTRUSTED_TAG}", f"<\\/{UNTRUSTED_TAG}")
    return f'<{UNTRUSTED_TAG} source="{source}">\n{safe}\n</{UNTRUSTED_TAG}>'


def approved(name: str, tool_input: dict, confirm: Confirm) -> bool:
    """Ask a human. If the confirmation itself fails, the answer is no."""
    try:
        return bool(confirm(name, tool_input))
    except Exception:
        log.exception("confirmation failed for %s: refused", name)
        return False


def run_tool_calls(
    response, toolbox: Toolbox, on_event: Callable[[dict], None], confirm: Confirm = refuse_all
) -> list[dict]:
    """Run every tool call of a response and return one `tool_result` for each."""
    results = []
    for block in response.content:
        if block.type != "tool_use":
            continue
        source = toolbox.source_of(block.name)
        log.info("tool_call %s from %s: %s", block.name, source, block.input)
        on_event({"type": "tool_call", "name": block.name, "input": block.input, "source": source})
        if toolbox.needs_confirmation(block.name):
            allowed = approved(block.name, block.input, confirm)
            log.info("confirmation %s: %s", block.name, "yes" if allowed else "no")
            on_event({"type": "confirmation", "name": block.name, "approved": allowed})
        else:
            allowed = True
        if allowed:
            content, is_error = toolbox.run(block.name, block.input)
            content = content if is_error else wrap_untrusted(source, content)
        else:
            # A refusal is a result like any other: Claude reads it and adapts.
            content, is_error = REFUSED_MESSAGE, True
        log.info("tool_result %s: error=%s", block.name, is_error)
        on_event({"type": "tool_result", "name": block.name, "is_error": is_error})
        result = {"type": "tool_result", "tool_use_id": block.id, "content": content}
        if is_error:
            result["is_error"] = True
        results.append(result)
    return results


def call_cost(response) -> float:
    """Return the cost of one response. A model without a price is billed as the default one."""
    try:
        return cost_usd(response.model, response.usage)
    except ValueError:
        return cost_usd(default_model(), response.usage)


def guarded(breaker: CircuitBreaker | None, call):
    """Run a call under the breaker, if there is one."""
    return breaker.call(call) if breaker else call()


def run_agent(
    client,
    messages: list[dict],
    toolbox: Toolbox,
    *,
    system: str,
    effort: str = "medium",
    tool_choice: dict | None = None,
    max_iterations: int = MAX_ITERATIONS,
    budget_usd: float = DEFAULT_BUDGET_USD,
    confirm: Confirm = refuse_all,
    breaker: CircuitBreaker | None = None,
    on_event: Callable[[dict], None] = lambda event: None,
) -> AgentResult:
    """Loop until Claude has finished. The model decides the steps, `stop_reason` drives the loop.

    `messages` is extended in place, so a conversation can go on after the run.
    `tool_choice` is passed to the API as is, e.g. {"type": "tool", "name": "get_weather"}.
    Two guards stop a run that goes on too long: `max_iterations` turns, and `budget_usd` spent.
    `confirm(name, input)` decides about the tools that need a human (default: always no).
    When the API stays down after the retries (or the `breaker` is open) or the user's quota is
    spent, the run ends with a message instead of an exception: `unavailable`, `quota_exceeded`.
    """
    response = None
    spent = 0.0
    for iteration in range(1, max_iterations + 1):
        started_at = time.monotonic()
        try:
            response = guarded(
                breaker,
                lambda: with_retry(
                    lambda: send(
                        client,
                        messages,
                        system=system,
                        tools=toolbox.definitions(),
                        tool_choice=tool_choice,
                        effort=effort,
                    )
                ),
            )
        except QuotaExceededError as error:
            log.warning("quota exceeded: %s", error)
            return AgentResult(str(error), "quota_exceeded", iteration, spent)
        except (*RETRYABLE, CircuitOpenError) as error:
            log.error("API unavailable after %d turns: %s", iteration, error)
            return AgentResult(DEGRADED_MESSAGE, "unavailable", iteration, spent)
        spent += call_cost(response)
        on_event(
            {
                "type": "response",
                "iteration": iteration,
                "response": response,
                "duration_ms": round((time.monotonic() - started_at) * 1000),
            }
        )

        if response.stop_reason == "refusal":
            return AgentResult(text_of(response), "refusal", iteration, spent)

        # A finished answer is never thrown away, but a run that wants to go on must stay in budget.
        if response.stop_reason in ("tool_use", "pause_turn") and spent >= budget_usd:
            log.warning("budget of %.2f USD reached after %d turns", budget_usd, iteration)
            on_event({"type": "stop", "reason": "budget_limit", "cost_usd": spent})
            return AgentResult(text_of(response), "budget_limit", iteration, spent)

        # Append the whole content, not only the text: thinking blocks must be sent back.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            messages.append(
                {
                    "role": "user",
                    "content": run_tool_calls(response, toolbox, on_event, confirm),
                }
            )
        elif response.stop_reason == "pause_turn":
            # The server paused a long turn: sending the history back resumes it.
            continue
        else:
            # end_turn, max_tokens or anything else: there is nothing left to run.
            # A tool call cut by max_tokens has no result, and the next request would be rejected.
            if any(block.type == "tool_use" for block in response.content):
                messages.pop()
            return AgentResult(text_of(response), response.stop_reason, iteration, spent)

    # Our own guard: a model that keeps calling tools must not spend without limit.
    log.warning("iteration limit of %d reached", max_iterations)
    on_event({"type": "stop", "reason": "iteration_limit", "cost_usd": spent})
    return AgentResult(text_of(response), "iteration_limit", max_iterations, spent)
