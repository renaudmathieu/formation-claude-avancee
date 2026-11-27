"""The guards of the SDK agent. No call to the API: only decisions and declarations."""

import asyncio

import pytest

from escale import agent_sdk
from escale.config import ROOT


def is_denied(decision: dict) -> bool:
    return decision.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


BOOKING = {"hotel": "Hôtel des Traboules", "city": "Lyon", "nights": 2}


def test_booking_goes_through_when_a_human_says_yes():
    assert agent_sdk.booking_decision(BOOKING, lambda name, tool_input: True) == {}


def test_booking_is_refused_by_default():
    decision = agent_sdk.booking_decision(BOOKING, agent_sdk.refuse_all)

    assert is_denied(decision)
    assert "refusée" in decision["hookSpecificOutput"]["permissionDecisionReason"]


def test_booking_fails_closed_when_confirmation_breaks():
    def broken(name, tool_input):
        raise RuntimeError("no terminal")

    assert is_denied(agent_sdk.booking_decision(BOOKING, broken))


def test_writing_is_allowed_only_in_the_output_folder(tmp_path):
    assert agent_sdk.write_decision({"file_path": "sortie/lyon.md"}) == {}
    assert is_denied(agent_sdk.write_decision({"file_path": "escale/config.py"}))
    assert is_denied(agent_sdk.write_decision({"file_path": str(ROOT / "sortie/../.env")}))


def test_options_declare_tools_limits_and_hooks():
    pytest.importorskip("claude_agent_sdk")

    options = agent_sdk.build_options(budget_usd=0.5)

    assert options.permission_mode == "dontAsk"
    assert options.max_turns == agent_sdk.MAX_TURNS
    assert options.max_budget_usd == 0.5
    assert "Bash" in options.disallowed_tools
    assert "escale" in options.mcp_servers
    matchers = [m.matcher for m in options.hooks["PreToolUse"]]
    assert matchers == [agent_sdk.BOOKING, "Write|Edit"]


def test_the_booking_hook_answers_like_the_sdk_expects():
    pytest.importorskip("claude_agent_sdk")
    hook = agent_sdk.build_options().hooks["PreToolUse"][0].hooks[0]

    decision = asyncio.run(hook({"tool_input": BOOKING}, "toolu_1", None))

    assert is_denied(decision)
