-- Meta-Ausgaben pro Tag über alle Kampagnen.

select
    spend_date,
    sum(spend_eur)      as spend_eur,
    sum(impressions)    as impressions,
    sum(clicks)         as clicks

from {{ ref('stg_meta__insights') }}
group by spend_date
