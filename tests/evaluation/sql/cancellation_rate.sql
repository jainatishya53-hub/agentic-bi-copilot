SELECT
    DATE_TRUNC('month', order_date)::date AS month,
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (
        WHERE status = 'cancelled'
    ) AS cancelled_orders,
    ROUND(
        (
            COUNT(*) FILTER (
                WHERE status = 'cancelled'
            ) * 100.0
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS cancellation_rate_pct
FROM orders
WHERE order_date >= DATE '2026-02-01'
  AND order_date < DATE '2026-08-01'
GROUP BY
    DATE_TRUNC('month', order_date)::date
ORDER BY
    month
LIMIT 500;