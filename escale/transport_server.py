"""MCP server exposing a fictional train and hotel catalogue.

Run it with `uv run python -m escale.transport_server`. The agent discovers these tools at
start-up: none of them is defined in the agent's code.
"""

import argparse

from mcp.server.mcpserver import MCPServer

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# Fictional data. Some hotels are deliberately above the ceilings of the travel policy.
TRAINS = [
    {"from": "Paris", "to": "Lyon", "train": "TF 6614", "depart": "07:42", "arrive": "09:38"},
    {"from": "Paris", "to": "Lyon", "train": "TF 6622", "depart": "09:58", "arrive": "11:54"},
    {"from": "Paris", "to": "Lyon", "train": "TF 6640", "depart": "17:58", "arrive": "19:54"},
    {"from": "Lyon", "to": "Paris", "train": "TF 6617", "depart": "07:04", "arrive": "09:00"},
    {"from": "Lyon", "to": "Paris", "train": "TF 6639", "depart": "18:04", "arrive": "20:00"},
    {"from": "Paris", "to": "Nantes", "train": "TF 8815", "depart": "08:50", "arrive": "11:02"},
    {"from": "Nantes", "to": "Paris", "train": "TF 8864", "depart": "17:30", "arrive": "19:42"},
]
# Same price in both directions: every fictional route goes through Paris.
SECOND_CLASS_PRICES = {"Lyon": 62, "Nantes": 54}
HOTELS = [
    {"city": "Lyon", "name": "Hôtel des Traboules", "stars": 3, "price_per_night_eur": 118},
    {"city": "Lyon", "name": "Le Confluent", "stars": 4, "price_per_night_eur": 139},
    {"city": "Lyon", "name": "Grand Palais Bellecour", "stars": 5, "price_per_night_eur": 289},
    {"city": "Lyon", "name": "Résidence Part-Dieu", "stars": 4, "price_per_night_eur": 165},
    {"city": "Nantes", "name": "Hôtel de l'Erdre", "stars": 3, "price_per_night_eur": 104},
    {"city": "Nantes", "name": "Le Graslin", "stars": 4, "price_per_night_eur": 152},
    {"city": "Paris", "name": "Hôtel du Canal", "stars": 3, "price_per_night_eur": 172},
    {"city": "Paris", "name": "Le Marais Royal", "stars": 4, "price_per_night_eur": 240},
]

server = MCPServer(
    name="escale-transport",
    instructions="Catalogue fictif de trains et d'hôtels, pour la formation.",
)


def _same(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


@server.tool()
def search_trains(origin: str, destination: str) -> list[dict]:
    """Cherche les trains directs entre deux villes, avec horaires et prix en seconde classe.

    Args:
        origin: Ville de départ, par exemple Paris.
        destination: Ville d'arrivée, par exemple Lyon.
    """
    return [
        {
            **train,
            "second_class_price_eur": SECOND_CLASS_PRICES[
                train["to"] if train["to"] != "Paris" else train["from"]
            ],
        }
        for train in TRAINS
        if _same(train["from"], origin) and _same(train["to"], destination)
    ]


@server.tool()
def search_hotels(city: str) -> list[dict]:
    """Cherche les hôtels d'une ville, avec leur catégorie et leur prix par nuit.

    Args:
        city: Ville recherchée, par exemple Lyon.
    """
    return [hotel for hotel in HOTELS if _same(hotel["city"], city)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur MCP de démonstration")
    parser.add_argument("--host", default=DEFAULT_HOST, help="0.0.0.0 pour un serveur partagé")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    print(f"Serveur MCP sur http://{args.host}:{args.port}/mcp")
    server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
