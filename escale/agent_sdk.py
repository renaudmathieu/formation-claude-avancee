"""The same Escale agent, written with the Claude Agent SDK instead of our own loop.

`escale/agent.py` owns every turn: the loop, the budget, the confirmation. Here the SDK
runs the Claude Code harness and we only declare what the agent may do. The guards are
the same, moved to where the SDK expects them: hooks and permission rules.

Install the optional dependency first: `uv sync --extra sdk`.
Run: `uv run python -m escale.agent_sdk "Prépare mes deux jours à Lyon"`.
"""

import asyncio
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from escale.assistant import OUTPUT_DIR, system_prompt
from escale.config import ROOT, agent_budget, default_model

MAX_TURNS = 20
BOOKING = "mcp__escale__book_hotel"

# Read-only by default. Writing is allowed, but a hook keeps it inside sortie/.
ALLOWED_TOOLS = ["mcp__escale__search_travel_policy", BOOKING, "Read", "Glob", "Grep", "Write"]
# No shell and no web for this agent: it has nothing to do there.
DISALLOWED_TOOLS = ["Bash", "WebFetch", "WebSearch"]

ESCALE_MCP = {
    "type": "stdio",
    "command": "uv",
    "args": ["run", "python", "-m", "escale.mcp_server"],
}

Confirm = Callable[[str, dict], bool]


def refuse_all(name: str, tool_input: dict) -> bool:
    """Headless default: nobody to answer, so an irreversible action is refused."""
    return False


def deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def booking_decision(tool_input: dict, confirm: Confirm) -> dict:
    """Ask a human before a booking. If asking fails, the answer is no."""
    try:
        if confirm(BOOKING, tool_input):
            return {}
    except Exception:  # noqa: BLE001
        return deny("Confirmation impossible : réservation refusée.")
    return deny("Réservation refusée par l'utilisateur. Ne réessaie pas, propose une alternative.")


def write_decision(tool_input: dict, output_dir: Path = ROOT / OUTPUT_DIR) -> dict:
    """Writing is allowed only inside the output folder."""
    target = Path(tool_input.get("file_path", ""))
    if not target.is_absolute():
        target = ROOT / target
    if target.resolve().is_relative_to(output_dir.resolve()):
        return {}
    return deny(f"Écriture refusée hors de {OUTPUT_DIR}/ : {target.name}.")


def build_options(confirm: Confirm = refuse_all, budget_usd: float | None = None):
    """Declare the agent: tools, permissions, guards and limits. Nothing runs here."""
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

    async def guard_booking(input_data, tool_use_id, context):
        return booking_decision(input_data["tool_input"], confirm)

    async def guard_write(input_data, tool_use_id, context):
        return write_decision(input_data["tool_input"])

    return ClaudeAgentOptions(
        model=default_model(),
        system_prompt=system_prompt(date.today()),
        cwd=str(ROOT),
        mcp_servers={"escale": ESCALE_MCP},
        allowed_tools=ALLOWED_TOOLS,
        disallowed_tools=DISALLOWED_TOOLS,
        # Anything not allowed above is refused without asking: nobody is there to answer.
        permission_mode="dontAsk",
        max_turns=MAX_TURNS,
        max_budget_usd=budget_usd if budget_usd is not None else agent_budget(),
        hooks={
            "PreToolUse": [
                HookMatcher(matcher=BOOKING, hooks=[guard_booking], on_failure="block"),
                HookMatcher(matcher="Write|Edit", hooks=[guard_write], on_failure="block"),
            ]
        },
    )


async def run(task: str, confirm: Confirm = refuse_all) -> int:
    """Run one task headless, print what the agent says, end with its cost."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, query

    async for message in query(prompt=task, options=build_options(confirm)):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0
            print(f"\n[{message.num_turns} tours, fin : {message.subtype}, coût {cost:.4f} $]")
            return 1 if message.is_error else 0
    return 1


def ask_in_terminal(name: str, tool_input: dict) -> bool:
    answer = input(f"\n{name} {tool_input} : confirmer ? [o/N] ")
    return answer.strip().lower() in {"o", "oui"}


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage : uv run python -m escale.agent_sdk "tâche"')
        return 2
    # Like the other commands: the key and ESCALE_MODEL come from the trainee's own file.
    load_dotenv()
    confirm = ask_in_terminal if sys.stdin.isatty() else refuse_all
    return asyncio.run(run(sys.argv[1], confirm))


if __name__ == "__main__":
    sys.exit(main())
