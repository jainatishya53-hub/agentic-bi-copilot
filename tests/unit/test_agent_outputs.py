from agentic_bi_copilot.agent.nodes import FOLLOW_UP_QUESTIONS


def test_agent_defines_three_grounded_follow_up_questions() -> None:
    assert len(FOLLOW_UP_QUESTIONS) == 3
    assert len(set(FOLLOW_UP_QUESTIONS)) == 3
    assert all(question.endswith("?") for question in FOLLOW_UP_QUESTIONS)
