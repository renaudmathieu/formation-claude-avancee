import json

from escale import extraction
from evals import run
from tests.fakes import FakeClient, response, text

LEON = {"date": "2026-11-17", "category": "restaurant", "amount_eur": 34.8, "vendor": "Chez Léon"}


def test_identical_expenses_pass():
    assert run.score_case([LEON], [LEON]) == []


def test_vendor_case_and_amount_noise_are_tolerated():
    got = {**LEON, "vendor": "chez léon ", "amount_eur": 34.80001}

    assert run.score_case([got], [LEON]) == []


def test_wrong_amount_is_a_failure():
    problems = run.score_case([{**LEON, "amount_eur": 3.48}], [LEON])

    assert len(problems) == 2  # the right one is missing, the wrong one is extra
    assert problems[0].startswith("manquante")


def test_an_invented_expense_is_a_failure():
    assert run.score_case([LEON], []) == [f"en trop : {LEON}"]


def test_order_does_not_matter():
    other = {**LEON, "category": "taxi", "vendor": "VTC Lumo"}

    assert run.score_case([other, LEON], [LEON, other]) == []


def test_the_cases_match_the_receipts_and_the_schema():
    cases = run.load_cases()

    assert len(cases) == 10
    assert any(case["attendu"] == [] for case in cases)
    for case in cases:
        for expense in case["attendu"]:
            assert expense["category"] in extraction.CATEGORIES


def test_run_and_report_count_the_failures():
    cases = [
        {"justificatif": "10-diner-leon", "attendu": [LEON]},
        {"justificatif": "09-taxi-illisible", "attendu": []},
    ]
    good = response(text(json.dumps({"expenses": [LEON]})))
    invented = response(text(json.dumps({"expenses": [LEON]})))

    results = run.run(FakeClient(good, invented), "v2", cases)
    report = run.report(results, "v2")

    assert results["10-diner-leon"] == []
    assert results["09-taxi-illisible"] != []
    assert "1/2" in report
    assert "ECHEC 09-taxi-illisible" in report
