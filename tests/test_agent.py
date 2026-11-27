import anthropic

from escale.agent import run_agent
from escale.toolbox import Tool, Toolbox, ToolError
from tests.fakes import FakeClient, api_error, response, text, thinking, tool_use


def echo_tool(calls: list | None = None) -> Tool:
    def handler(tool_input: dict) -> str:
        if calls is not None:
            calls.append(tool_input)
        return f"echo {tool_input['value']}"

    return Tool(definition={"name": "echo"}, handler=handler)


def failing_tool() -> Tool:
    def handler(tool_input: dict) -> str:
        raise ToolError("panne")

    return Tool(definition={"name": "broken"}, handler=handler)


def start(question: str = "Prépare mon voyage") -> list[dict]:
    return [{"role": "user", "content": question}]


def run(client, tools, **kwargs):
    return run_agent(client, start(), Toolbox(tools), system="s", **kwargs)


def test_loop_continues_until_end_turn():
    calls = []
    client = FakeClient(
        response(tool_use("echo", {"value": 1}), stop_reason="tool_use"),
        response(tool_use("echo", {"value": 2}), stop_reason="tool_use"),
        response(text("Terminé")),
    )

    result = run(client, [echo_tool(calls)])

    assert result.text == "Terminé"
    assert result.is_complete
    assert result.iterations == 3
    assert calls == [{"value": 1}, {"value": 2}]


def test_answer_without_tool_stops_at_once():
    client = FakeClient(response(text("Bonjour")))

    assert run(client, [echo_tool()]).iterations == 1


def test_all_parallel_results_share_one_message():
    client = FakeClient(
        response(
            tool_use("echo", {"value": 1}, "a"),
            tool_use("echo", {"value": 2}, "b"),
            stop_reason="tool_use",
        ),
        response(text("OK")),
    )

    run(client, [echo_tool()])

    last = client.requests[1]["messages"][-1]
    assert last["role"] == "user"
    assert [result["tool_use_id"] for result in last["content"]] == ["a", "b"]


def test_thinking_blocks_are_sent_back_unchanged():
    block = thinking("je réfléchis")
    client = FakeClient(
        response(block, tool_use("echo", {"value": 1}), stop_reason="tool_use"),
        response(text("OK")),
    )

    run(client, [echo_tool()])

    sent = client.requests[1]["messages"][1]["content"][0]
    assert (sent.type, sent.thinking, sent.signature) == ("thinking", "je réfléchis", "sig")


def test_tool_failure_goes_back_to_claude_and_the_loop_goes_on():
    client = FakeClient(
        response(tool_use("broken", {}), stop_reason="tool_use"),
        response(text("Je contourne")),
    )

    result = run(client, [failing_tool()])

    tool_result = client.requests[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True
    assert tool_result["content"] == "panne"
    assert result.text == "Je contourne"


def test_unknown_tool_is_an_error_result():
    client = FakeClient(
        response(tool_use("inconnu", {}), stop_reason="tool_use"),
        response(text("OK")),
    )

    run(client, [echo_tool()])

    assert client.requests[1]["messages"][-1]["content"][0]["is_error"] is True


def test_iteration_limit_stops_a_runaway_agent():
    client = FakeClient(
        *[response(tool_use("echo", {"value": i}), stop_reason="tool_use") for i in range(5)]
    )

    result = run(client, [echo_tool()], max_iterations=3)

    assert result.stop_reason == "iteration_limit"
    assert result.iterations == 3
    assert len(client.requests) == 3


def test_pause_turn_resumes_without_a_new_user_message():
    client = FakeClient(response(stop_reason="pause_turn"), response(text("Repris")))

    result = run(client, [echo_tool()])

    assert result.text == "Repris"
    assert client.requests[1]["messages"][-1]["role"] == "assistant"


def test_max_tokens_is_not_reported_as_complete():
    client = FakeClient(response(text("Début"), stop_reason="max_tokens"))

    result = run(client, [echo_tool()])

    assert result.stop_reason == "max_tokens"
    assert not result.is_complete


def test_refusal_stops_without_running_anything():
    calls = []
    client = FakeClient(response(stop_reason="refusal"))

    result = run(client, [echo_tool(calls)])

    assert result.stop_reason == "refusal"
    assert calls == []


def test_events_describe_the_run():
    events = []
    client = FakeClient(
        response(tool_use("echo", {"value": 1}), stop_reason="tool_use"),
        response(text("OK")),
    )

    run(client, [echo_tool()], on_event=events.append)

    assert [event["type"] for event in events] == [
        "response",
        "tool_call",
        "tool_result",
        "response",
    ]


def test_unexpected_tool_failure_goes_back_to_claude():
    def crash(tool_input: dict) -> str:
        raise ValueError("embedded null byte")

    client = FakeClient(
        response(tool_use("crash", {}), stop_reason="tool_use"),
        response(text("Je contourne")),
    )

    result = run(client, [Tool(definition={"name": "crash"}, handler=crash)])

    tool_result = client.requests[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True
    assert "embedded null byte" in tool_result["content"]
    assert result.text == "Je contourne"


def test_tool_call_cut_by_max_tokens_is_not_kept_in_the_history():
    messages = start()
    client = FakeClient(response(tool_use("echo", {}), stop_reason="max_tokens"))

    result = run_agent(client, messages, Toolbox([echo_tool()]), system="s")

    assert result.stop_reason == "max_tokens"
    assert [message["role"] for message in messages] == ["user"]


def test_first_tool_wins_when_two_share_a_name():
    local = Tool(definition={"name": "echo"}, handler=lambda tool_input: "local")
    remote = Tool(definition={"name": "echo"}, handler=lambda tool_input: "remote")

    assert Toolbox([local, remote]).run("echo", {}) == ("local", False)


def test_tool_choice_is_passed_to_the_api():
    client = FakeClient(response(text("OK")))
    choice = {"type": "tool", "name": "echo"}

    run(client, [echo_tool()], tool_choice=choice)

    assert client.requests[0]["tool_choice"] == choice


def test_transient_api_error_is_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    client = FakeClient(api_error(anthropic.RateLimitError, 429), response(text("OK")))

    assert run(client, [echo_tool()]).text == "OK"
    assert len(client.requests) == 2
