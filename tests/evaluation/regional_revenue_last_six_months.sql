WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', o.order_date)::date AS month,
        r.name AS region,
        ROUND(
            SUM(oi.quantity * oi.unit_price),
            2
        ) AS revenue
    FROM orders AS o
    JOIN customers AS c
        ON c.customer_id = o.customer_id
    JOIN regions AS r
        ON r.region_id = c.region_id
    JOIN order_items AS oi
        ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
      AND o.order_date >= DATE '2026-01-01'
      AND o.order_date < DATE '2026-08-01'
    GROUP BY
        DATE_TRUNC('month', o.order_date)::date,
        r.name
),
revenue_with_previous_month AS (
    SELECT
        month,
        region,
        revenue,
        LAG(revenue) OVER (
            PARTITION BY region
            ORDER BY month
        ) AS previous_month_revenue
    FROM monthly_revenue
),
calculated_changes AS (
    SELECT
        month,
        region,
        revenue,
        previous_month_revenue,
        ROUND(
            (
                (revenue - previous_month_revenue)
                / NULLIF(previous_month_revenue, 0)
            ) * 100,
            2
        ) AS month_over_month_change_pct
    FROM revenue_with_previous_month
)
SELECT
    month,
    region,
    revenue,
    previous_month_revenue,
    month_over_month_change_pct,
    month_over_month_change_pct <= -20 AS unusual_decline
FROM calculated_changes
WHERE month >= DATE '2026-02-01'
ORDER BY
    region,
    month
LIMIT 500;