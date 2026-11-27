import json

import pytest

from escale.tools import booking


def test_booking_appends_and_never_overwrites(tmp_path):
    path = tmp_path / "sortie" / "reservations.jsonl"

    first = booking.book_hotel("Le Confluent", "Lyon", 2, path)
    second = booking.book_hotel("Le Graslin", "Nantes", 1, path)

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["reference"] for line in lines] == [first["reference"], second["reference"]]


@pytest.mark.parametrize(
    ("hotel", "city", "nights"),
    [("", "Lyon", 1), ("Le Confluent", " ", 1), ("Le Confluent", "Lyon", 0)],
)
def test_invalid_booking_writes_nothing(tmp_path, hotel, city, nights):
    path = tmp_path / "reservations.jsonl"

    with pytest.raises(ValueError):
        booking.book_hotel(hotel, city, nights, path)

    assert not path.exists()
