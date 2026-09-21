{{ config(severity = 'warn') }}

-- Ein Tag mit Meta-Spend, aber ohne eine einzige Bestellung kann auf einen Ladefehler
-- bei Shopify oder auf ein Problem im Shop, zum Beispiel beim Checkout, hindeuten.
-- Als Warnung, damit dbt build weiterläuft und der Alert es getrennt vom ROAS meldet.

select
    report_date,
    meta_spend_eur
from {{ ref('fct_marketing_performance') }}
where meta_spend_eur > 0
  and orders = 0
