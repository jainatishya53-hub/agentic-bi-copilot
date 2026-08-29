WITH category_revenue AS (
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
)
SELECT
    category,
    total_revenue,
    ROUND(
        (
            total_revenue
            / NULLIF(
                SUM(total_revenue) OVER (),
                0
            )
        ) * 100,
        2
    ) AS contribution_pct
FROM category_revenue
ORDER BY
    contribution_pct DESC,
    category
LIMIT 500;