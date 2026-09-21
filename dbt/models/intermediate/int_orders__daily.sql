-- Bestellungen pro Tag, inklusive Neukunden.

with orders as (

    select * from {{ ref('stg_shopify__orders') }}

),

first_orders as (

    select * from {{ ref('int_customers__first_order') }}

)

select
    o.order_date,
    count(distinct o.order_id)                          as orders,
    sum(o.order_value_eur)                              as revenue_eur,

    -- Neukunde = Kunde, dessen erste Bestellung an diesem Tag war.
    -- Mehrere Bestellungen am ersten Tag zählen trotzdem nur einmal.
    count(distinct case
        when o.order_date = f.first_order_date then o.customer_id
    end)                                                as new_customers,

    -- Gastbestellungen ohne customer_id: keinem Kunden zuordenbar.
    countif(o.customer_id is null)                      as orders_without_customer,

    -- Rabattcodes deuten oft auf Influencer oder E-Mail hin, nicht auf Meta.
    countif(o.discount_code is not null)                as orders_with_discount

from orders as o
left join first_orders as f
    on o.customer_id = f.customer_id
group by o.order_date
