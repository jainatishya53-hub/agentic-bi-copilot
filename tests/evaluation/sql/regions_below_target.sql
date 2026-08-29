WITH regional_revenue AS (
    SELECT
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
      AND o.order_date >= DATE '2026-07-01'
      AND o.order_date < DATE '2026-08-01'
    GROUP BY
        c.region_id
)
SELECT
    r.name AS region,
    COALESCE(rr.revenue, 0) AS revenue,
    mt.revenue_target,
    ROUND(
        COALESCE(rr.revenue, 0) - mt.revenue_target,
        2
    ) AS target_variance
FROM monthly_targets AS mt
JOIN regions AS r
    ON r.region_id = mt.region_id
LEFT JOIN regional_revenue AS rr
    ON rr.region_id = mt.region_id
WHERE mt.month = DATE '2026-07-01'
  AND COALESCE(rr.revenue, 0) < mt.revenue_target
ORDER BY
    target_variance,
    r.name
LIMIT 500;