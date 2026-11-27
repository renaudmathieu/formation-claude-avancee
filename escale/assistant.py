"""What makes this agent Escale: its instructions, its tools and how it shows its work."""

from datetime import date
from pathlib import Path

from escale.agent import AgentResult, run_agent
from escale.config import agent_budget, agent_effort
from escale.llm import cached_text
from escale.mcp_client import McpUnavailableError, load_mcp_tools, mcp_deferred, mcp_url
from escale.prompts import load_prompt
from escale.resilience import CircuitBreaker
from escale.toolbox import Tool, Toolbox
from escale.tools.booking import booking_tool
from escale.tools.files import file_tools
from escale.tools.policy import policy_tool
from escale.tools.weather import weather_tool

OUTPUT_DIR = Path("sortie")
# One breaker for the whole process: it remembers that the API is down between questions.
BREAKER = CircuitBreaker()
REFUSAL_MESSAGE = "Je ne peux pas répondre à cette demande."
TRUNCATED_MESSAGE = "\n[Réponse coupée : limite de tokens atteinte.]"
LIMIT_MESSAGE = "\n[Arrêt : limite de tours atteinte, le travail est peut-être incomplet.]"
BUDGET_MESSAGE = "\n[Arrêt : budget de la tâche atteint, le travail est peut-être incomplet.]"


def system_blocks(today: date) -> list[dict]:
    """The system prompt as two blocks: the stable instructions (cached), then today's date.

    Claude does not know the date unless we tell it. It goes AFTER the cached block: a date in
    front would change the prefix every day and the cache would never be read.
    """
    return [*cached_text(load_prompt("assistant").text), {"type": "text", "text": date_line(today)}]


def date_line(today: date) -> str:
    return f"Nous sommes le {today.isoformat()}."


def system_prompt(today: date) -> str:
    """The same prompt as one text (for tests and for reading)."""
    return "\n\n".join(block["text"] for block in system_blocks(today))


def remote_tools() -> list[Tool]:
    """Load the MCP tools. An unavailable server must not prevent the agent from working."""
    url = mcp_url()
    try:
        tools = load_mcp_tools(url, deferred=mcp_deferred())
    except McpUnavailableError as error:
        print(f"[mcp] Serveur injoignable ({url}), l'agent continue sans lui : {error}")
        return []
    print(f"[mcp] {url} : {', '.join(tool.name for tool in tools)}")
    return tools


def build_toolbox() -> Toolbox:
    """Gather the tools the agent can use, local first, then remote."""
    return Toolbox(
        [weather_tool(), policy_tool(), *file_tools(OUTPUT_DIR), booking_tool(), *remote_tools()]
    )


def describe(result: AgentResult) -> str:
    """Turn the way a run ended into what the user reads."""
    if result.stop_reason == "refusal":
        return REFUSAL_MESSAGE
    if result.stop_reason == "max_tokens":
        return result.text + TRUNCATED_MESSAGE
    if result.stop_reason == "iteration_limit":
        return result.text + LIMIT_MESSAGE
    if result.stop_reason == "budget_limit":
        return result.text + BUDGET_MESSAGE
    return result.text


def show_progress(event: dict) -> None:
    """Print what the agent is doing, so that the loop can be seen."""
    if event["type"] == "response":
        response = event["response"]
        for block in response.content:
            if block.type == "thinking" and block.thinking:
                print(f"[réflexion] {block.thinking}")
        print(f"[tour {event['iteration']}] stop_reason={response.stop_reason}")
    elif event["type"] == "tool_call":
        print(f"[tool:{event['source']}] {event['name']} {_shorten(str(event['input']))}")
    elif event["type"] == "confirmation":
        print(f"[confirmation] {event['name']} : {'accordée' if event['approved'] else 'refusée'}")
    elif event["type"] == "tool_result" and event["is_error"]:
        print(f"[tool] {event['name']} a échoué")


def _shorten(value: str, limit: int = 200) -> str:
    return value if len(value) <= limit else f"{value[:limit]}..."


def confirm_in_terminal(name: str, tool_input: dict) -> bool:
    """Ask the user before an action nobody can undo. Anything but "o" means no."""
    print(f"\nL'agent veut exécuter {name} avec {tool_input}.")
    return input("Confirmer ? [o/N] ").strip().lower() in ("o", "oui")


def run_task(
    client,
    task: str,
    toolbox: Toolbox | None = None,
    *,
    effort: str | None = None,
    budget_usd: float | None = None,
    confirm=confirm_in_terminal,
) -> AgentResult:
    """Give the agent one task and let it work until it has finished.

    `effort` and `budget_usd` default to the environment (`ESCALE_EFFORT`, `ESCALE_BUDGET_USD`).
    """
    return run_agent(
        client,
        [{"role": "user", "content": task}],
        toolbox or build_toolbox(),
        system=system_blocks(date.today()),
        effort=effort or agent_effort(),
        budget_usd=agent_budget() if budget_usd is None else budget_usd,
        confirm=confirm,
        breaker=BREAKER,
        on_event=show_progress,
    )
