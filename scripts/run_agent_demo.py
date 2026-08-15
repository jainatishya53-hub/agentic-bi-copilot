import json
from uuid import uuid4

from langgraph.types import Command

from agentic_bi_copilot.agent.graph import build_agent_graph

QUESTION = (
    "Compare revenue across regions for the last six complete months "
    "and identify unusual declines."
)


def main() -> None:
    graph = build_agent_graph()
    config = {
        "configurable": {
            "thread_id": str(uuid4()),
        }
    }

    print("Starting agent workflow...")
    paused = graph.invoke(
        {"question": QUESTION},
        config=config,
    )

    interrupts = paused.get("__interrupt__", ())

    if not interrupts:
        print("The workflow ended before human approval.")
        print(json.dumps(paused, indent=2, default=str))
        return

    approval_request = interrupts[0].value

    print("\nAnalysis question:")
    print(approval_request["question"])

    print("\nSQL explanation:")
    print(approval_request["sql_explanation"])

    print("\nReferenced tables:")
    print(", ".join(approval_request["referenced_tables"]))

    print("\nSafety validation:")
    print(
        json.dumps(
            approval_request["validation"],
            indent=2,
            default=str,
        )
    )

    print("\nGenerated SQL:")
    print(approval_request["sql"])

    answer = input(
        "\nType APPROVE to execute this SQL; "
        "anything else will reject it: "
    ).strip()

    approved = answer == "APPROVE"
    feedback = None

    if not approved:
        feedback = (
            input("Optional rejection reason: ").strip()
            or "Rejected during interactive review."
        )

    completed = graph.invoke(
        Command(
            resume={
                "approved": approved,
                "feedback": feedback,
            }
        ),
        config=config,
    )

    if not approved:
        print("\nExecution rejected. No query was run.")
        print("Reason:", completed["rejection_reason"])
        return

    query_result = completed["query_result"]
    rows = query_result["rows"]

    print("\nExecution completed.")
    print("Rows:", query_result["row_count"])
    print(
        "Execution time:",
        f"{query_result['execution_time_ms']:.2f} ms",
    )
    print("\nBusiness answer:")
    print(completed["answer"])

    print(
        "Chart traces:",
        len(completed["chart"].get("data", [])),
    )

    print("\nUnusual declines:")

    for row in rows:
        if row.get("unusual_decline"):
            print(
                f"- {row['region']} | {row['month']} | "
                f"{row['month_over_month_change_pct']}%"
            )


if __name__ == "__main__":
    main()