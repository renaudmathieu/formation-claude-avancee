"""Escale as an MCP server, for Claude Code or any other MCP client.

Run it with `uv run python -m escale.mcp_server` (stdio). The server name is part of the tool
names seen by Claude Code (`mcp__escale__book_hotel`): changing it breaks the permission rules.

It is a thin facade: the search is the one of section 4, the booking is `tools/booking.py`.
"""

import json
import logging
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from escale.tools import booking, policy

SERVER_NAME = "escale"
POLICY_URI = "escale://politique"

# In stdio, stdout IS the JSON-RPC channel: a print() would corrupt it. Log to stderr.
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("escale.mcp")


def create_server(reservations: Path = booking.RESERVATIONS_FILE) -> MCPServer:
    """Build the server. `reservations` lets tests book into a temporary file."""
    server = MCPServer(
        SERVER_NAME,
        instructions="Escale : la politique de voyage de l'entreprise et la réservation d'hôtels.",
    )

    @server.tool(
        name="search_travel_policy",
        # One source of truth: the description written for the agent in section 4.
        description=policy.POLICY_TOOL["description"],
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def search_travel_policy(
        query: Annotated[
            str,
            Field(
                min_length=1,
                max_length=200,
                description="Mots-clés, par exemple : plafond hôtel Paris.",
            ),
        ],
        limit: Annotated[int, Field(ge=1, le=10, description="Nombre maximal de passages.")] = 5,
    ) -> str:
        log.info("search_travel_policy query=%r", query)
        # `policy.search` is called through the module: the same code as the agent, not a copy.
        results = policy.search(query, limit)
        if not results:
            return "Aucun passage de la politique ne correspond à cette recherche."
        return json.dumps(results, ensure_ascii=False)

    @server.resource(
        POLICY_URI,
        name="politique",
        description="Liste des pages de la politique de voyage.",
        mime_type="application/json",
    )
    def policy_pages() -> str:
        # Names only: the client chooses what to load, and a long text is not copied for nothing.
        return json.dumps([page.stem for page in policy.pages()], ensure_ascii=False)

    @server.tool(
        name="book_hotel",
        description=(
            "Réserve un hôtel pour un déplacement. Cette action est définitive : une réservation "
            "engage l'entreprise. N'utilise cet outil que si l'utilisateur a demandé cette "
            "réservation précise (hôtel, ville, nombre de nuits) et l'a confirmée."
        ),
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True),
    )
    def book_hotel(
        hotel: Annotated[str, Field(min_length=1, max_length=100, description="Nom de l'hôtel.")],
        city: Annotated[
            str, Field(min_length=1, max_length=60, description="Ville, par exemple Lyon.")
        ],
        nights: Annotated[int, Field(ge=1, le=booking.MAX_NIGHTS, description="Nombre de nuits.")],
    ) -> str:
        log.info("book_hotel hotel=%r city=%r nights=%d", hotel, city, nights)
        # The file is fixed by the server, never an argument: arguments come from the model.
        made = booking.book_hotel(hotel, city, nights, reservations)
        return (
            f"Réservation {made['reference']} : {made['hotel']}, {made['city']}, {nights} nuit(s)."
        )

    return server


server = create_server()

if __name__ == "__main__":
    server.run("stdio")
