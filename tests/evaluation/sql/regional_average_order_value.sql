WITH order_totals AS (
    SELECT
        o.order_id,
        r.name AS region,
        SUM(
            oi.quantity * oi.unit_price
        ) AS order_revenue
    FROM orders AS o
    JOIN customers AS c
        ON c.customer_id = o.customer_id
    JOIN regions AS r
        ON r.region_id = c.region_id
    JOIN order_items AS oi
        ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
      AND o.order_date >= DATE '2026-02-01'
      AND o.order_date < DATE '2026-08-01'
    GROUP BY
        o.order_id,
        r.name
)
SELECT
    region,
    COUNT(*) AS completed_orders,
    ROUND(
        SUM(order_revenue),
        2
    ) AS total_revenue,
    ROUND(
        AVG(order_revenue),
        2
    ) AS average_order_value
FROM order_totals
GROUP BY
    region
ORDER BY
    average_order_value DESC,
    region
LIMIT 500;