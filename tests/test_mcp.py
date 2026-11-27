import json

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as ServerToolError

from escale import assistant
from escale.agent import run_agent
from escale.mcp_client import load_mcp_tools
from escale.toolbox import Toolbox
from escale.transport_server import server
from tests.fakes import FakeClient, response, text, tool_use


def test_tools_are_discovered_with_their_schema():
    tools = {tool.name: tool for tool in load_mcp_tools(server)}

    assert set(tools) == {"search_trains", "search_hotels"}
    schema = tools["search_trains"].definition["input_schema"]
    assert schema["required"] == ["origin", "destination"]
    assert tools["search_hotels"].definition["description"]


def test_remote_tool_returns_the_catalogue():
    box = Toolbox(load_mcp_tools(server))

    content, is_error = box.run("search_hotels", {"city": "lyon"})

    assert not is_error
    assert "Hôtel des Traboules" in content
    assert "Hôtel de l'Erdre" not in content


def test_train_search_filters_on_both_cities():
    box = Toolbox(load_mcp_tools(server))

    content, _ = box.run("search_trains", {"origin": "Paris", "destination": "Nantes"})

    assert "TF 8815" in content
    assert "TF 6614" not in content
    assert json.loads(content)


def test_server_side_failure_becomes_an_error_result():
    broken = MCPServer(name="broken")

    @broken.tool()
    def fail() -> str:
        """Always fails."""
        raise ServerToolError("panne du catalogue")

    content, is_error = Toolbox(load_mcp_tools(broken)).run("fail", {})

    assert is_error
    assert "panne du catalogue" in content


def test_agent_can_use_a_tool_it_only_knows_through_mcp():
    client = FakeClient(
        response(tool_use("search_hotels", {"city": "Lyon"}), stop_reason="tool_use"),
        response(text("Hôtel trouvé")),
    )
    box = Toolbox(load_mcp_tools(server))

    result = run_agent(client, [{"role": "user", "content": "Un hôtel ?"}], box, system="s")

    assert result.text == "Hôtel trouvé"
    assert "search_hotels" in [tool["name"] for tool in client.requests[0]["tools"]]
    assert "Traboules" in client.requests[1]["messages"][-1]["content"][0]["content"]


def test_unreachable_server_does_not_stop_the_agent(monkeypatch, capsys):
    # Port 9 is closed on the local machine: the failure is real, without leaving the machine.
    monkeypatch.setenv("ESCALE_MCP_URL", "http://127.0.0.1:9/mcp")

    assert assistant.remote_tools() == []
    assert "injoignable" in capsys.readouterr().out


def test_a_route_costs_the_same_in_both_directions():
    box = Toolbox(load_mcp_tools(server))

    there, _ = box.run("search_trains", {"origin": "Paris", "destination": "Nantes"})
    back, _ = box.run("search_trains", {"origin": "Nantes", "destination": "Paris"})

    assert '"second_class_price_eur": 54' in there
    assert '"second_class_price_eur": 54' in back


def test_deferred_tools_stay_out_of_the_context_until_searched():
    box = Toolbox([assistant.weather_tool(), *load_mcp_tools(server, deferred=True)])

    definitions = box.definitions()

    deferred = [d["name"] for d in definitions if d.get("defer_loading")]
    assert set(deferred) == {"search_trains", "search_hotels"}
    assert not definitions[0].get("defer_loading")
    assert [d for d in definitions if d.get("type", "").startswith("tool_search")] == [
        definitions[-1]
    ]


def test_without_deferred_tools_no_search_tool_is_sent():
    definitions = Toolbox(load_mcp_tools(server)).definitions()

    assert not any("defer_loading" in d or "type" in d for d in definitions)


def test_deferred_mode_is_read_from_the_environment(monkeypatch):
    from escale.mcp_client import mcp_deferred

    monkeypatch.setenv("ESCALE_MCP_DIFFERE", "1")
    assert mcp_deferred()
    monkeypatch.delenv("ESCALE_MCP_DIFFERE")
    assert not mcp_deferred()
