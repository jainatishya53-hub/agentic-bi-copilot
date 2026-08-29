WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', o.order_date)::date AS month,
        c.region_id,
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
      AND o.order_date >= DATE '2026-02-01'
      AND o.order_date < DATE '2026-08-01'
    GROUP BY
        DATE_TRUNC('month', o.order_date)::date,
        c.region_id
)
SELECT
    mt.month,
    r.name AS region,
    COALESCE(mr.revenue, 0) AS revenue,
    mt.revenue_target,
    ROUND(
        COALESCE(mr.revenue, 0) - mt.revenue_target,
        2
    ) AS target_variance,
    ROUND(
        (
            COALESCE(mr.revenue, 0)
            / NULLIF(mt.revenue_target, 0)
        ) * 100,
        2
    ) AS target_achievement_pct
FROM monthly_targets AS mt
JOIN regions AS r
    ON r.region_id = mt.region_id
LEFT JOIN monthly_revenue AS mr
    ON mr.region_id = mt.region_id
   AND mr.month = mt.month
WHERE mt.month >= DATE '2026-02-01'
  AND mt.month < DATE '2026-08-01'
ORDER BY
    mt.month,
    r.name
LIMIT 500;
