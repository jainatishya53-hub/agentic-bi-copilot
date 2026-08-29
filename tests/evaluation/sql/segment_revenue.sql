SELECT
    c.segment,
    ROUND(
        SUM(oi.quantity * oi.unit_price),
        2
    ) AS total_revenue
FROM orders AS o
JOIN customers AS c
    ON c.customer_id = o.customer_id
JOIN order_items AS oi
    ON oi.order_id = o.order_id
WHERE o.status = 'completed'
  AND o.order_date >= DATE '2026-02-01'
  AND o.order_date < DATE '2026-08-01'
GROUP BY
    c.segment
ORDER BY
    total_revenue DESC,
    c.segment
LIMIT 500;