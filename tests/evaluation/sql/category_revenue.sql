SELECT
    p.category,
    ROUND(
        SUM(oi.quantity * oi.unit_price),
        2
    ) AS total_revenue
FROM orders AS o
JOIN order_items AS oi
    ON oi.order_id = o.order_id
JOIN products AS p
    ON p.product_id = oi.product_id
WHERE o.status = 'completed'
  AND o.order_date >= DATE '2026-02-01'
  AND o.order_date < DATE '2026-08-01'
GROUP BY
    p.category
ORDER BY
    total_revenue DESC,
    p.category
LIMIT 500;
