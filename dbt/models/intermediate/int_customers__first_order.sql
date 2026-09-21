-- Erste Bestellung pro Kunde. Grundlage für die Neukunden-Zählung im CAC.
-- Wichtig: Die Historie muss bis zum Shop-Start zurückreichen.
-- Sonst werden Bestandskunden fälschlich als Neukunden gezählt.

select
    customer_id,
    min(order_date) as first_order_date

from {{ ref('stg_shopify__orders') }}
where customer_id is not null
group by customer_id
