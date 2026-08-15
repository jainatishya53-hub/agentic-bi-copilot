import json
from uuid import uuid4

from langgraph.types import Command

from agentic_bi_copilot.agent.graph import build_agent_graph

QUESTION = (
    "Compare revenue across regions for the last six complete months "
    "and identify unusual declines."
)

APPROVAL_WORD = "APPROVE"


def create_graph_config() -> dict[str, dict[str, str]]:
    # LangGraph uses the thread ID to find and continue a paused run.
    thread_id = str(uuid4())

    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


def print_json(value: object) -> None:
    formatted_value = json.dumps(
        value,
        indent=2,
        default=str,
    )

    print(formatted_value)


def display_approval_request(
    approval_request: dict[str, object],
) -> None:
    print("\nAnalysis question:")
    print(approval_request["question"])

    print("\nSQL explanation:")

    sql_explanation = approval_request.get("sql_explanation")

    if sql_explanation:
        print(sql_explanation)
    else:
        print("No SQL explanation was provided.")

    print("\nReferenced tables:")
    referenced_tables = approval_request["referenced_tables"]
    print(", ".join(referenced_tables))

    print("\nSafety validation:")
    print_json(approval_request["validation"])

    print("\nGenerated SQL:")
    print(approval_request["sql"])


def ask_for_approval() -> tuple[bool, str | None]:
    answer = input(
        "\nType APPROVE to execute this SQL; anything else will reject it: "
    ).strip()

    # Only the exact approval word allows database execution.
    approved = answer == APPROVAL_WORD

    if approved:
        return True, None

    rejection_reason = input("Optional rejection reason: ").strip()

    if not rejection_reason:
        rejection_reason = "Rejected during interactive review."

    return False, rejection_reason


def display_rejection(
    completed_state: dict[str, object],
) -> None:
    print("\nExecution rejected. No query was run.")
    print(
        "Reason:",
        completed_state["rejection_reason"],
    )


def display_unusual_declines(
    rows: list[dict[str, object]],
) -> None:
    print("\nUnusual declines:")

    # Only display rows marked by the deterministic analysis query.
    for row in rows:
        if not row.get("unusual_decline"):
            continue

        print(
            f"- {row['region']} | "
            f"{row['month']} | "
            f"{row['month_over_month_change_pct']}%"
        )


def display_completed_result(
    completed_state: dict[str, object],
) -> None:
    query_result = completed_state["query_result"]
    rows = query_result["rows"]

    print("\nExecution completed.")
    print(
        "Rows:",
        query_result["row_count"],
    )
    print(
        "Execution time:",
        (f"{query_result['execution_time_ms']:.2f} ms"),
    )

    print("\nBusiness answer:")
    print(completed_state["answer"])

    chart = completed_state["chart"]
    chart_traces = len(chart.get("data", []))

    print(
        "Chart traces:",
        chart_traces,
    )

    display_unusual_declines(rows)


def main() -> None:
    graph = build_agent_graph()
    config = create_graph_config()

    print("Starting agent workflow...")

    paused_state = graph.invoke(
        {
            "question": QUESTION,
        },
        config=config,
    )

    interrupts = paused_state.get(
        "__interrupt__",
        (),
    )

    if not interrupts:
        print("The workflow ended before human approval.")
        print_json(paused_state)
        return

    approval_request = interrupts[0].value

    display_approval_request(approval_request)

    approved, feedback = ask_for_approval()

    # Resume the same paused thread with the reviewer's decision.
    completed_state = graph.invoke(
        Command(
            resume={
                "approved": approved,
                "feedback": feedback,
            }
        ),
        config=config,
    )

    if not approved:
        display_rejection(completed_state)
        return

    display_completed_result(completed_state)


if __name__ == "__main__":
    main()
