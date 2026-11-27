"""The agent loop: call Claude, run the tools it asks for, and start again."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from escale.llm import send, text_of, with_retry
from escale.toolbox import Toolbox

MAX_ITERATIONS = 20


@dataclass(frozen=True)
class AgentResult:
    """How a run ended. `stop_reason` is the API's, or `iteration_limit` for our own guard."""

    text: str
    stop_reason: str
    iterations: int

    @property
    def is_complete(self) -> bool:
        return self.stop_reason == "end_turn"


def run_tool_calls(response, toolbox: Toolbox, on_event: Callable[[dict], None]) -> list[dict]:
    """Run every tool call of a response and return one `tool_result` for each."""
    results = []
    for block in response.content:
        if block.type != "tool_use":
            continue
        on_event(
            {
                "type": "tool_call",
                "name": block.name,
                "input": block.input,
                "source": toolbox.source_of(block.name),
            }
        )
        content, is_error = toolbox.run(block.name, block.input)
        on_event({"type": "tool_result", "name": block.name, "is_error": is_error})
        result = {"type": "tool_result", "tool_use_id": block.id, "content": content}
        if is_error:
            result["is_error"] = True
        results.append(result)
    return results


def run_agent(
    client,
    messages: list[dict],
    toolbox: Toolbox,
    *,
    system: str,
    effort: str = "medium",
    tool_choice: dict | None = None,
    max_iterations: int = MAX_ITERATIONS,
    on_event: Callable[[dict], None] = lambda event: None,
) -> AgentResult:
    """Loop until Claude has finished. The model decides the steps, `stop_reason` drives the loop.

    `messages` is extended in place, so a conversation can go on after the run.
    `tool_choice` is passed to the API as is, e.g. {"type": "tool", "name": "get_weather"}.
    """
    response = None
    for iteration in range(1, max_iterations + 1):
        started_at = time.monotonic()
        response = with_retry(
            lambda: send(
                client,
                messages,
                system=system,
                tools=toolbox.definitions(),
                tool_choice=tool_choice,
                effort=effort,
            )
        )
        on_event(
            {
                "type": "response",
                "iteration": iteration,
                "response": response,
                "duration_ms": round((time.monotonic() - started_at) * 1000),
            }
        )

        if response.stop_reason == "refusal":
            return AgentResult(text_of(response), "refusal", iteration)

        # Append the whole content, not only the text: thinking blocks must be sent back.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            messages.append(
                {"role": "user", "content": run_tool_calls(response, toolbox, on_event)}
            )
        elif response.stop_reason == "pause_turn":
            # The server paused a long turn: sending the history back resumes it.
            continue
        else:
            # end_turn, max_tokens or anything else: there is nothing left to run.
            # A tool call cut by max_tokens has no result, and the next request would be rejected.
            if any(block.type == "tool_use" for block in response.content):
                messages.pop()
            return AgentResult(text_of(response), response.stop_reason, iteration)

    # Our own guard: a model that keeps calling tools must not spend without limit.
    return AgentResult(text_of(response), "iteration_limit", max_iterations)
