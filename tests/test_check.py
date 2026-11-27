import json

import pytest

from escale import __main__ as cli
from escale import check
from tests.fakes import FakeClient, response, text


def expense(category, amount, vendor="Fournisseur"):
    return {"date": "2026-11-18", "category": category, "amount_eur": amount, "vendor": vendor}


def answer(*expenses):
    return response(text(json.dumps({"expenses": list(expenses)})))


def test_ceilings_are_read_in_the_policy_pages():
    ceilings, pages = check.ceilings_for("taxi")

    assert ceilings == [35.0]
    assert pages == ["transport"]


def test_taxi_under_the_ceiling_is_compliant_and_cites_the_page():
    finding = check.check_expense(expense("taxi", 28.5))

    assert finding.verdict == check.COMPLIANT
    assert finding.page == "transport"


def test_taxi_over_the_ceiling_is_flagged():
    assert check.check_expense(expense("taxi", 41)).verdict == check.OVER


def test_hotel_above_every_ceiling_is_flagged_with_its_page():
    finding = check.check_expense(expense("hotel", 200))

    assert finding.verdict == check.OVER
    assert finding.page == "hebergement"


def test_missing_city_is_declared_instead_of_guessed():
    # 160 € is fine in Paris (185 €) and too much elsewhere (140 €): the receipt has no city.
    finding = check.check_expense(expense("hotel", 160))

    assert finding.verdict == check.TO_CHECK
    assert "140 €" in finding.detail
    assert "185 €" in finding.detail


def test_category_without_ceiling_says_so():
    finding = check.check_expense(expense("train", 62))

    assert finding.verdict == check.NO_CEILING
    assert finding.page is None


def test_changing_the_policy_changes_the_verdict(tmp_path, monkeypatch):
    (tmp_path / "taxi.md").write_text(
        "# Taxi\n\n## Course\n\nTaxi et VTC : plafond de 20 € par course."
    )
    monkeypatch.setenv("ESCALE_POLITIQUE", str(tmp_path))

    finding = check.check_expense(expense("taxi", 28.5))

    assert finding.verdict == check.OVER
    assert finding.page == "taxi"


def test_check_note_extracts_then_checks_each_expense():
    client = FakeClient(answer(expense("taxi", 28.5), expense("taxi", 50)))

    findings = check.check_note(client, "note de frais")

    assert [finding.verdict for finding in findings] == [check.COMPLIANT, check.OVER]


def test_format_finding_shows_the_verdict_and_the_page():
    line = check.format_finding(check.check_expense(expense("taxi", 50, "Taxis Bleus")))

    assert "AU-DESSUS DU PLAFOND" in line
    assert "Taxis Bleus" in line
    assert line.endswith("page transport")


@pytest.fixture
def cli_with_fake_client(monkeypatch):
    def install(client):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        monkeypatch.setattr(cli, "load_dotenv", lambda: None)
        monkeypatch.setattr(cli.anthropic, "Anthropic", lambda: client)

    return install


def test_check_command_prints_each_verdict_and_fails_on_a_ceiling(
    tmp_path, monkeypatch, capsys, cli_with_fake_client
):
    note = tmp_path / "note.md"
    note.write_text("Taxi 50 €", encoding="utf-8")
    cli_with_fake_client(FakeClient(answer(expense("taxi", 50))))
    monkeypatch.setattr("sys.argv", ["escale", "check", str(note)])

    assert cli.main() == 1
    assert "AU-DESSUS DU PLAFOND" in capsys.readouterr().out


def test_check_command_succeeds_when_everything_is_compliant(
    tmp_path, monkeypatch, capsys, cli_with_fake_client
):
    note = tmp_path / "note.md"
    note.write_text("Taxi 20 €", encoding="utf-8")
    cli_with_fake_client(FakeClient(answer(expense("taxi", 20))))
    monkeypatch.setattr("sys.argv", ["escale", "check", str(note)])

    assert cli.main() == 0
    assert "CONFORME" in capsys.readouterr().out
