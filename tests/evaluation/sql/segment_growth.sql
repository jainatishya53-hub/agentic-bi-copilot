WITH monthly_segment_revenue AS (
    SELECT
        DATE_TRUNC('month', o.order_date)::date AS month,
        c.segment,
        ROUND(
            SUM(oi.quantity * oi.unit_price),
            2
        ) AS revenue
    FROM orders AS o
    JOIN customers AS c
        ON c.customer_id = o.customer_id
    JOIN order_items AS oi
        ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
      AND o.order_date >= DATE '2026-01-01'
      AND o.order_date < DATE '2026-08-01'
    GROUP BY
        DATE_TRUNC('month', o.order_date)::date,
        c.segment
),
revenue_with_previous_month AS (
    SELECT
        month,
        segment,
        revenue,
        LAG(revenue) OVER (
            PARTITION BY segment
            ORDER BY month
        ) AS previous_month_revenue
    FROM monthly_segment_revenue
)
SELECT
    month,
    segment,
    revenue,
    previous_month_revenue,
    ROUND(
        (
            (revenue - previous_month_revenue)
            / NULLIF(previous_month_revenue, 0)
        ) * 100,
        2
    ) AS growth_pct
FROM revenue_with_previous_month
WHERE month >= DATE '2026-02-01'
ORDER BY
    segment,
    month
LIMIT 500;