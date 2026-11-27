"""A fictional hotel booking. It cannot be undone, so it is the tool that needs a guard."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from escale.config import ROOT

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
