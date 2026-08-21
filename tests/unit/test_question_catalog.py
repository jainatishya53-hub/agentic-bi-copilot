import pytest

from agentic_bi_copilot.services.question_catalog import (
    QUESTION_EXAMPLES,
    get_question_example,
    list_example_questions,
)


def test_catalog_contains_twelve_questions() -> None:
    assert len(QUESTION_EXAMPLES) == 12
    assert len(list_example_questions()) == 12


def test_question_keys_are_unique() -> None:
    keys = [example.key for example in QUESTION_EXAMPLES]

    assert len(keys) == len(set(keys))


def test_questions_are_unique() -> None:
    questions = list_example_questions()

    assert len(questions) == len(set(questions))


def test_every_question_defines_expected_tables() -> None:
    for example in QUESTION_EXAMPLES:
        assert example.expected_tables
        assert all(example.expected_tables)


def test_catalog_covers_different_analysis_types() -> None:
    analysis_types = {example.analysis_type for example in QUESTION_EXAMPLES}

    assert analysis_types == {
        "time_series",
        "ranking",
        "target_comparison",
        "segment_comparison",
        "rate_analysis",
        "contribution_analysis",
    }


def test_get_question_example_returns_matching_example() -> None:
    example = get_question_example("top_products")

    assert example.title == "Top products"
    assert "products" in example.expected_tables


def test_get_question_example_rejects_unknown_key() -> None:
    with pytest.raises(
        KeyError,
        match="Unknown question example",
    ):
        get_question_example("unknown")
