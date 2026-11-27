from datetime import date

from escale.agent import AgentResult
from escale.assistant import build_toolbox, describe, run_task, system_prompt
from escale.toolbox import Toolbox
from tests.fakes import FakeClient, response, text, tool_use


def test_system_prompt_gives_today_s_date():
    assert "2026-11-26" in system_prompt(date(2026, 11, 26))


def test_toolbox_holds_the_policy_weather_and_file_tools():
    assert set(build_toolbox().tools) == {
        "get_weather",
        "search_travel_policy",
        "read_file",
        "write_file",
    }


def test_describe_flags_an_incomplete_run():
    assert "limite de tours" in describe(AgentResult("Début", "iteration_limit", 20))
    assert describe(AgentResult("", "refusal", 1)) == "Je ne peux pas répondre à cette demande."


def test_agent_answers_a_policy_question_with_the_search_tool(capsys):
    client = FakeClient(
        response(
            tool_use("search_travel_policy", {"query": "plafond hôtel"}), stop_reason="tool_use"
        ),
        response(text("185 € à Paris (page hebergement).")),
    )

    result = run_task(
        client, "Plafond d'hôtel ?", Toolbox([build_toolbox().tools["search_travel_policy"]])
    )

    assert result.is_complete
    sent = client.requests[1]["messages"][-1]["content"][0]["content"]
    assert "hebergement" in sent
    assert "tool:local" in capsys.readouterr().out
