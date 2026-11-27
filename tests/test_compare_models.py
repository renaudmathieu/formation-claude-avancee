import pytest

from escale import config
from scripts import compare_models
from tests.fakes import FakeClient, response, text


def make_client():
    # Six answers: 2 tasks x 3 models, each with its own token counts.
    return FakeClient(
        *[
            response(text("réponse"), input_tokens=1_000_000, output_tokens=1_000_000)
            for _ in range(6)
        ]
    )


def test_both_tasks_run_on_the_three_models():
    client = make_client()

    rows = compare_models.compare(client)

    assert [row.model for row in rows] == list(compare_models.MODELS) * 2
    assert [request["model"] for request in client.requests] == [row.model for row in rows]
    assert {row.task for row in rows} == {"résumé", "classification"}


def test_summary_task_sends_the_accommodation_page():
    client = make_client()

    compare_models.compare(client)

    assert "185 €" in client.requests[0]["messages"][0]["content"]


def test_cost_comes_from_the_config_prices():
    rows = compare_models.compare(make_client())

    assert rows[0].cost == pytest.approx(0.60)  # Haiku: 0.10 + 0.50
    assert rows[1].cost == pytest.approx(12.0)  # Sonnet: 2 + 10
    assert rows[2].model == config.MODEL_SMART
    assert rows[2].cost == pytest.approx(24.0)  # Opus: 4 + 20


def test_duration_uses_the_injected_clock():
    ticks = iter([0.0, 1.5])

    row = compare_models.measure(
        FakeClient(response(text("oui"))), "classification", "?", config.MODEL_FAST, ticks.__next__
    )

    assert row.seconds == 1.5


def test_table_has_one_line_per_measure():
    rows = compare_models.compare(make_client())

    lines = compare_models.format_table(rows).splitlines()

    assert len(lines) == 2 + 6
    assert "claude-haiku-5-5" in lines[2]
