import json

import anyio
import pytest
from mcp import Client

from escale import mcp_server
from escale.tools import policy


def with_client(server, action):
    """Connect an in-memory MCP client to `server` and run `action`: no process, no network."""

    async def main():
        async with Client(server) as client:
            return await action(client)

    return anyio.run(main)


def call(server, name, arguments):
    return with_client(server, lambda client: client.call_tool(name, arguments))


def text_of(result) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


@pytest.fixture
def server(tmp_path):
    return mcp_server.create_server(tmp_path / "reservations.jsonl")


def test_server_name_matches_the_claude_code_tool_names():
    assert mcp_server.SERVER_NAME == "escale"


def test_server_exposes_the_two_tools(server):
    tools = {tool.name: tool for tool in with_client(server, lambda c: c.list_tools()).tools}

    assert set(tools) == {"search_travel_policy", "book_hotel"}
    assert tools["book_hotel"].input_schema["required"] == ["hotel", "city", "nights"]
    assert tools["search_travel_policy"].description == policy.POLICY_TOOL["description"]


def test_search_is_a_facade_over_the_section_4_code(server, monkeypatch):
    calls = []

    def spy(query, limit=5):
        calls.append((query, limit))
        return [{"page": "espion", "excerpt": "Trouvé par l'espion."}]

    monkeypatch.setattr(policy, "search", spy)

    result = call(server, "search_travel_policy", {"query": "plafond", "limit": 3})

    assert calls == [("plafond", 3)]
    assert "espion" in text_of(result)


def test_search_returns_the_page_and_its_excerpt(server):
    result = call(server, "search_travel_policy", {"query": "plafond hôtel Paris"})

    assert not result.is_error
    first = json.loads(text_of(result))[0]
    assert first["page"] == "hebergement"
    assert "185 €" in first["excerpt"]


def test_search_reads_the_folder_of_the_environment(server, tmp_path, monkeypatch):
    (tmp_path / "seminaires.md").write_text("# Séminaires\n\n## Budget\n\nBudget : 90 € par jour.")
    monkeypatch.setenv("ESCALE_POLITIQUE", str(tmp_path))

    result = call(server, "search_travel_policy", {"query": "budget"})

    assert json.loads(text_of(result))[0]["page"] == "seminaires"


def test_search_rejects_an_out_of_range_limit(server):
    assert call(server, "search_travel_policy", {"query": "taxi", "limit": 99}).is_error


def test_resource_lists_the_policy_pages(server):
    reply = with_client(server, lambda client: client.read_resource("escale://politique"))

    pages = json.loads("".join(content.text for content in reply.contents))
    assert pages == ["hebergement", "notes-de-frais", "repas", "transport"]


def test_booking_appends_one_line_to_the_reservations_file(server, tmp_path):
    result = call(server, "book_hotel", {"hotel": "Le Confluent", "city": "Lyon", "nights": 2})

    assert not result.is_error
    lines = (tmp_path / "reservations.jsonl").read_text(encoding="utf-8").splitlines()
    booking = json.loads(lines[0])
    assert (booking["hotel"], booking["city"], booking["nights"]) == ("Le Confluent", "Lyon", 2)
    assert booking["reference"] in text_of(result)


@pytest.mark.parametrize("nights", [0, 31, -1])
def test_booking_refuses_a_wrong_number_of_nights(server, tmp_path, nights):
    result = call(server, "book_hotel", {"hotel": "Le Confluent", "city": "Lyon", "nights": nights})

    assert result.is_error
    assert not (tmp_path / "reservations.jsonl").exists()


def test_booking_is_marked_as_destructive(server):
    tools = {tool.name: tool for tool in with_client(server, lambda c: c.list_tools()).tools}

    assert tools["book_hotel"].annotations.destructive_hint is True
    assert tools["search_travel_policy"].annotations.read_only_hint is True


def test_claude_code_config_registers_the_server_and_denies_the_booking():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    mcp_config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))

    assert mcp_config["mcpServers"]["escale"]["args"][-1] == "escale.mcp_server"
    assert "mcp__escale__book_hotel" in settings["permissions"]["deny"]
