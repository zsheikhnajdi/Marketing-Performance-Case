-- Staging: Shopify-Bestellungen bereinigen.
-- Ergebnis: genau eine Zeile pro Bestellung, Datum in Europe/Berlin.

with source as (

    select * from {{ source('shopify', 'src_shopify_orders') }}

),

deduplicated as (

    -- Sicherheitsnetz: Im Merge-Modus ersetzt dlt alte Versionen selbst.
    -- Lädt eine Quelle im Append-Modus, kann dieselbe Bestellung aber mehrfach ankommen.
    -- Dann gewinnt das neueste Load Package. Dafür nutzen wir nur, dass die Load ID
    -- mit jeder Ladung steigt. Der Cast sorgt für eine numerische Sortierung statt
    -- einer alphabetischen, weil die ID als Text gespeichert ist.
    select
        *,
        row_number() over (
            partition by order_id
            order by cast(_dlt_load_id as float64) desc
        ) as row_num
    from source

)

select
    cast(order_id as string)                        as order_id,
    cast(customer_id as string)                     as customer_id,
    created_at                                      as created_at_utc,

    -- Shopify liefert UTC, Meta rechnet in der Zeitzone des Werbekontos
    -- (Annahme: Europe/Berlin). Ohne Umrechnung landen Bestellungen kurz nach
    -- Mitternacht am falschen Tag. Die Sommerzeit ist dabei berücksichtigt.
    date(created_at, 'Europe/Berlin')               as order_date,

    -- Geldbeträge nicht als FLOAT weiterrechnen: Rundungsfehler summieren sich.
    -- Hinweis: total_price enthält MwSt. und Versand (siehe Dokumentation).
    round(cast(total_price as numeric), 2)          as order_value_eur,

    nullif(trim(discount_code), '')                 as discount_code

from deduplicated
where row_num = 1
