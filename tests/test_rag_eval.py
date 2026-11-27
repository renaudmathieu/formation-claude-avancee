"""Section 9: the evaluation set and the recall measure."""

import json

import pytest

from escale import rag
from escale.config import DATA_DIR
from evals import run_rag
from tests.fakes import concept_embedder


def test_the_set_has_24_questions_with_one_out_of_corpus_and_one_exact_reference():
    questions = run_rag.load_questions()

    assert len(questions) == 24
    assert [q["id"] for q in questions if q["page"] is None] == ["q24"]
    assert sum(q["category"] == "référence exacte" for q in questions) == 1


def test_every_page_of_the_policy_holds_at_least_one_answer():
    pages = {q["page"] for q in run_rag.load_questions()}

    assert {page.stem for page in DATA_DIR.glob("*.md")} <= pages


def test_the_exact_reference_question_is_won_by_keywords():
    question = next(q for q in run_rag.load_questions() if q["category"] == "référence exacte")
    index = rag.build_index(DATA_DIR, concept_embedder)

    assert index.pages(question["question"], 1, "keyword") == [question["page"]]


def test_a_typo_in_an_expected_page_is_refused(tmp_path):
    file = tmp_path / "q.json"
    file.write_text(json.dumps({"questions": [{"id": "q1", "question": "?", "page": "repsa"}]}))

    with pytest.raises(ValueError, match="repsa"):
        run_rag.load_questions(file)


def test_a_duplicate_id_is_refused(tmp_path):
    question = {"id": "q1", "question": "?", "page": None}
    file = tmp_path / "q.json"
    file.write_text(json.dumps({"questions": [question, question]}))

    with pytest.raises(ValueError, match="double"):
        run_rag.load_questions(file)


def test_recall_looks_only_at_the_first_k_pages():
    assert run_rag.recall_at_k(["a", "b", "c"], "c", 3) == 1.0
    assert run_rag.recall_at_k(["a", "b", "c"], "c", 2) == 0.0


def test_evaluate_lists_failures_and_skips_out_of_corpus_questions():
    questions = [
        {"id": "q1", "question": "un", "page": "a"},
        {"id": "q2", "question": "deux", "page": "b"},
        {"id": "q3", "question": "trois", "page": None},
    ]

    result = run_rag.evaluate(lambda question, k: ["a"], questions)

    assert result == {"n": 2, "recall": 0.5, "failures": ["q2"]}


def test_the_three_versions_are_measured_on_the_same_questions():
    searches = run_rag.versions(DATA_DIR, concept_embedder)
    questions = run_rag.load_questions()

    results = {name: run_rag.evaluate(search, questions) for name, search in searches.items()}

    assert list(results) == ["mots-clés (BM25)", "hybride", "hybride + contexte"]
    assert {result["n"] for result in results.values()} == {23}
    assert all(result["recall"] >= 0.9 for result in results.values())
    assert "Recall@5 sur 23 questions" in run_rag.report(results)
