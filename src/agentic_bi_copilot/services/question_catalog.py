from dataclasses import dataclass

TIME_SERIES = "time_series"
RANKING = "ranking"
TARGET_COMPARISON = "target_comparison"
SEGMENT_COMPARISON = "segment_comparison"
RATE_ANALYSIS = "rate_analysis"
CONTRIBUTION_ANALYSIS = "contribution_analysis"


@dataclass(frozen=True, slots=True)
class QuestionExample:
    """Describe one analytics question shown by the application."""

    key: str
    title: str
    question: str
    analysis_type: str
    expected_tables: tuple[str, ...]


QUESTION_EXAMPLES = (
    QuestionExample(
        key="regional_revenue_declines",
        title="Regional revenue and declines",
        question=(
            "Compare revenue across regions for the last six complete "
            "months and identify unusual declines."
        ),
        analysis_type=TIME_SERIES,
        expected_tables=(
            "customers",
            "order_items",
            "orders",
            "regions",
        ),
    ),
    QuestionExample(
        key="monthly_revenue",
        title="Monthly revenue trend",
        question=("Show total revenue for each of the last six complete months."),
        analysis_type=TIME_SERIES,
        expected_tables=(
            "order_items",
            "orders",
        ),
    ),
    QuestionExample(
        key="top_products",
        title="Top products",
        question=(
            "Which 10 products generated the most revenue during the "
            "last six complete months?"
        ),
        analysis_type=RANKING,
        expected_tables=(
            "order_items",
            "orders",
            "products",
        ),
    ),
    QuestionExample(
        key="category_revenue",
        title="Revenue by category",
        question=(
            "Compare revenue by product category during the last six complete months."
        ),
        analysis_type=RANKING,
        expected_tables=(
            "order_items",
            "orders",
            "products",
        ),
    ),
    QuestionExample(
        key="regional_target_performance",
        title="Regional target performance",
        question=(
            "Compare actual revenue with monthly targets for each region "
            "during the last six complete months."
        ),
        analysis_type=TARGET_COMPARISON,
        expected_tables=(
            "customers",
            "monthly_targets",
            "order_items",
            "orders",
            "regions",
        ),
    ),
    QuestionExample(
        key="regions_below_target",
        title="Regions below target",
        question=(
            "Which regions missed their revenue targets during the last complete month?"
        ),
        analysis_type=TARGET_COMPARISON,
        expected_tables=(
            "customers",
            "monthly_targets",
            "order_items",
            "orders",
            "regions",
        ),
    ),
    QuestionExample(
        key="segment_revenue",
        title="Revenue by customer segment",
        question=(
            "Compare revenue by customer segment during the last six complete months."
        ),
        analysis_type=SEGMENT_COMPARISON,
        expected_tables=(
            "customers",
            "order_items",
            "orders",
        ),
    ),
    QuestionExample(
        key="segment_growth",
        title="Customer segment growth",
        question=(
            "Show monthly revenue growth for each customer segment during "
            "the last six complete months."
        ),
        analysis_type=TIME_SERIES,
        expected_tables=(
            "customers",
            "order_items",
            "orders",
        ),
    ),
    QuestionExample(
        key="cancellation_rate",
        title="Order cancellation rate",
        question=(
            "Show the monthly order cancellation rate for the last six complete months."
        ),
        analysis_type=RATE_ANALYSIS,
        expected_tables=("orders",),
    ),
    QuestionExample(
        key="top_customers",
        title="Top customers",
        question=(
            "Which 10 customers generated the most revenue during the "
            "last six complete months?"
        ),
        analysis_type=RANKING,
        expected_tables=(
            "customers",
            "order_items",
            "orders",
        ),
    ),
    QuestionExample(
        key="regional_average_order_value",
        title="Average order value by region",
        question=(
            "Compare average completed order value across regions during "
            "the last six complete months."
        ),
        analysis_type=SEGMENT_COMPARISON,
        expected_tables=(
            "customers",
            "order_items",
            "orders",
            "regions",
        ),
    ),
    QuestionExample(
        key="category_contribution",
        title="Category revenue contribution",
        question=(
            "What percentage of total revenue did each product category "
            "contribute during the last six complete months?"
        ),
        analysis_type=CONTRIBUTION_ANALYSIS,
        expected_tables=(
            "order_items",
            "orders",
            "products",
        ),
    ),
)


def list_example_questions() -> tuple[str, ...]:
    """Return the question text used by the interface."""

    return tuple(example.question for example in QUESTION_EXAMPLES)


def get_question_example(key: str) -> QuestionExample:
    """Find an example using its unique key."""

    for example in QUESTION_EXAMPLES:
        if example.key == key:
            return example

    raise KeyError(f"Unknown question example: {key}")
