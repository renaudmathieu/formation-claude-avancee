import json

from escale.toolbox import Toolbox
from escale.tools import policy


def test_search_finds_the_page_that_holds_the_ceiling():
    results = policy.search("plafond hôtel Paris")

    assert results[0]["page"] == "hebergement"
    assert "185 €" in results[0]["excerpt"]


def test_search_ignores_accents_and_case():
    assert policy.search("HOTEL")[0]["page"] == "hebergement"


def test_search_without_match_returns_nothing():
    assert policy.search("trottinette électrique") == []


def test_limit_bounds_the_number_of_results():
    assert len(policy.search("plafond", limit=2)) == 2


def test_pages_come_from_the_folder_in_the_environment(tmp_path, monkeypatch):
    (tmp_path / "seminaires.md").write_text("# Séminaires\n\n## Budget\n\nLe budget est de 90 €.")
    monkeypatch.setenv("ESCALE_POLITIQUE", str(tmp_path))

    assert [page.name for page in policy.pages()] == ["seminaires.md"]
    assert policy.search("budget")[0]["page"] == "seminaires"


def test_tool_returns_json_with_page_and_excerpt():
    content, is_error = Toolbox([policy.policy_tool()]).run(
        "search_travel_policy", {"query": "taxi plafond"}
    )

    assert not is_error
    assert {"page", "excerpt"} <= json.loads(content)[0].keys()


def test_empty_search_is_not_an_error():
    content, is_error = Toolbox([policy.policy_tool()]).run(
        "search_travel_policy", {"query": "trottinette"}
    )

    assert not is_error
    assert "Aucun passage" in content
