import json

import pytest

from escale import extraction
from tests.fakes import FakeClient, response, text

RECEIPT = "# Chez Léon\n17 novembre 2026\nTotal TTC : 34,80 €"
LEON = {"date": "2026-11-17", "category": "restaurant", "amount_eur": 34.8, "vendor": "Chez Léon"}


def answer(*expenses):
    return response(text(json.dumps({"expenses": list(expenses)})))


def test_expenses_are_returned_as_a_list_of_dicts():
    client = FakeClient(answer(LEON))

    assert extraction.extract_expenses(client, RECEIPT) == [LEON]


def test_request_asks_for_a_json_schema_and_sends_the_receipt():
    client = FakeClient(answer(LEON))

    extraction.extract_expenses(client, RECEIPT)

    request = client.requests[0]
    output_format = request["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["schema"] == extraction.SCHEMA
    assert request["messages"] == [{"role": "user", "content": RECEIPT}]


def test_prompt_version_selects_the_system_prompt():
    client = FakeClient(answer(), answer())

    extraction.extract_expenses(client, RECEIPT, "v1")
    extraction.extract_expenses(client, RECEIPT, "v2")

    assert "<role>" not in client.requests[0]["system"]
    assert "<role>" in client.requests[1]["system"]


def test_receipt_without_amount_gives_an_empty_list():
    client = FakeClient(answer())

    assert extraction.extract_expenses(client, "Montant : illisible") == []


def test_a_zero_amount_is_dropped():
    client = FakeClient(answer({**LEON, "amount_eur": 0}))

    assert extraction.extract_expenses(client, RECEIPT) == []


def test_unknown_prompt_version_is_an_error():
    with pytest.raises(ValueError, match="v9"):
        extraction.extract_expenses(FakeClient(), RECEIPT, "v9")


def test_cut_answer_is_reported_not_parsed():
    client = FakeClient(response(text('{"expenses": [{"da'), stop_reason="max_tokens"))

    with pytest.raises(ValueError, match="max_tokens"):
        extraction.extract_expenses(client, RECEIPT)
