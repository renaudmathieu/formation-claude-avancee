"""A fictional hotel booking. It cannot be undone, so it is the tool that needs a guard."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from escale.config import ROOT
from escale.toolbox import Tool, ToolError

RESERVATIONS_FILE = ROOT / "sortie" / "reservations.jsonl"
MAX_NIGHTS = 30


def book_hotel(hotel: str, city: str, nights: int, path: Path = RESERVATIONS_FILE) -> dict:
    """Book a hotel: append one line to the reservations file and return the booking.

    Nothing is sent anywhere, but the line is a commitment: calling this twice books twice.
    """
    if not hotel.strip() or not city.strip():
        raise ValueError("Il faut un nom d'hôtel et une ville.")
    if not 1 <= nights <= MAX_NIGHTS:
        raise ValueError(f"Le nombre de nuits doit être compris entre 1 et {MAX_NIGHTS}.")
    booking = {
        "reference": f"ESC-{uuid.uuid4().hex[:6].upper()}",
        "hotel": hotel.strip(),
        "city": city.strip(),
        "nights": nights,
        "booked_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(booking, ensure_ascii=False) + "\n")
    return booking


BOOKING_TOOL = {
    "name": "book_hotel",
    "description": (
        "Réserve un hôtel. Cette action est définitive : elle engage l'entreprise et demande "
        "l'accord de l'utilisateur. N'appelle cet outil que si l'utilisateur a lui-même demandé "
        "cette réservation précise (hôtel, ville, nombre de nuits)."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "hotel": {"type": "string", "description": "Nom de l'hôtel."},
            "city": {"type": "string", "description": "Ville, par exemple Lyon."},
            "nights": {"type": "integer", "description": "Nombre de nuits."},
        },
        "required": ["hotel", "city", "nights"],
        "additionalProperties": False,
    },
}


def booking_tool(path: Path = RESERVATIONS_FILE) -> Tool:
    """Build the booking tool for the agent. A human confirms every call (see `run_agent`)."""

    def handler(tool_input: dict) -> str:
        try:
            made = book_hotel(tool_input["hotel"], tool_input["city"], tool_input["nights"], path)
        except ValueError as error:
            raise ToolError(str(error)) from error
        return (
            f"Réservation {made['reference']} : {made['hotel']}, {made['city']}, "
            f"{made['nights']} nuit(s)."
        )

    return Tool(definition=BOOKING_TOOL, handler=handler, needs_confirmation=True)
