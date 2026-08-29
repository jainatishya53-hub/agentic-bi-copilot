SELECT
    DATE_TRUNC('month', o.order_date)::date AS month,
    ROUND(
        SUM(oi.quantity * oi.unit_price),
        2
    ) AS revenue
FROM orders AS o
JOIN order_items AS oi
    ON oi.order_id = o.order_id
WHERE o.status = 'completed'
  AND o.order_date >= DATE '2026-02-01'
  AND o.order_date < DATE '2026-08-01'
GROUP BY
    DATE_TRUNC('month', o.order_date)::date
ORDER BY
    month
LIMIT 500;