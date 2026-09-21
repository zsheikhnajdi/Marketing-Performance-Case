-- Staging: Meta-Insights bereinigen.
-- Ergebnis: genau eine Zeile pro Tag und Kampagne.

with source as (

    select * from {{ source('meta_ads', 'src_meta_insights') }}

),

deduplicated as (

    -- Meta-Werte können sich nachträglich ändern. Das Neuladen passiert in der
    -- Ingestion (dlt: attribution_window_days_lag), nicht hier in dbt.
    -- dbt sorgt nur dafür, dass pro Tag und Kampagne das neueste Ladepaket gewinnt.
    select
        *,
        row_number() over (
            partition by `date`, campaign_id
            order by cast(_dlt_load_id as float64) desc
        ) as row_num
    from source

)

select
    `date`                                          as spend_date,
    cast(campaign_id as string)                     as campaign_id,
    round(cast(spend as numeric), 2)                as spend_eur,
    impressions,
    clicks

from deduplicated
where row_num = 1
