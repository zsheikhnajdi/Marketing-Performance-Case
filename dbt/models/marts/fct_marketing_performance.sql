-- Eine Zeile pro Tag, auch an Tagen ohne Bestellungen oder ohne Spend.
-- Der heutige Tag wird bewusst nicht ausgewiesen: Die Pipeline läuft morgens,
-- ein halber Tag würde ROAS und Alert verfälschen.
-- Keine Partitionierung: Die Tabelle hat eine Zeile pro Tag und bleibt sehr klein.

with date_spine as (

    select report_date
    from unnest(
        generate_date_array(
            date('{{ var("reporting_start_date", "2025-01-01") }}'),
            date_sub(current_date('Europe/Berlin'), interval 1 day)
        )
    ) as report_date

),

orders as (

    select * from {{ ref('int_orders__daily') }}

),

spend as (

    select * from {{ ref('int_meta__daily') }}

),

daily as (

    select
        d.report_date,
        coalesce(s.spend_eur, 0)                    as meta_spend_eur,
        coalesce(o.revenue_eur, 0)                  as revenue_eur,
        coalesce(o.orders, 0)                       as orders,
        coalesce(o.new_customers, 0)                as new_customers,
        coalesce(s.clicks, 0)                       as clicks,
        coalesce(s.impressions, 0)                  as impressions,
        coalesce(o.orders_with_discount, 0)         as orders_with_discount,
        coalesce(o.orders_without_customer, 0)      as orders_without_customer
    from date_spine as d
    left join spend as s
        on s.spend_date = d.report_date
    left join orders as o
        on o.order_date = d.report_date

)

select
    report_date,
    meta_spend_eur,
    revenue_eur,
    orders,
    new_customers,

    -- Blended ROAS: Gesamtumsatz des Shops geteilt durch Meta-Ausgaben.
    -- Das ist NICHT der ROAS, den Meta selbst meldet (Meta-Attribution).
    -- SAFE_DIVIDE liefert NULL statt Fehler, wenn an einem Tag kein Spend war.
    safe_divide(revenue_eur, meta_spend_eur)                    as blended_roas,

    -- CAC nur über Neukunden, nicht über alle Bestellungen.
    -- Tag mit Spend, aber ohne Neukunden: CAC ist nicht definiert (NULL).
    safe_divide(meta_spend_eur, new_customers)                  as blended_cac_eur,

    -- 7-Tage-Werte: Ein Kauf passiert oft Tage nach dem Klick.
    -- Der Tageswert schwankt deshalb stark, für Entscheidungen ist der 7-Tage-Wert stabiler.
    -- In den ersten sechs Tagen der Historie ist das Fenster kürzer.
    safe_divide(
        sum(revenue_eur)    over last_7_days,
        sum(meta_spend_eur) over last_7_days
    )                                                           as blended_roas_7d,
    safe_divide(
        sum(meta_spend_eur) over last_7_days,
        sum(new_customers)  over last_7_days
    )                                                           as blended_cac_7d_eur,

    clicks,
    impressions,
    orders_with_discount,
    orders_without_customer

from daily
window last_7_days as (
    order by report_date
    rows between 6 preceding and current row
)
