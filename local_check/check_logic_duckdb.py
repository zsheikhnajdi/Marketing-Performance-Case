"""
Lokaler Test der Modelllogik mit Beispieldaten in DuckDB.

Nachgebaut werden staging, intermediate und fct_marketing_performance,
mit bewusst schwierigen Fällen und festen Erwartungswerten:
- doppelte Ladung derselben Bestellung
- Bestellung um 23:30 UTC, also am nächsten Tag in Berlin
- zwei Bestellungen desselben Kunden an seinem ersten Tag
- Wiederkäufer und Gastbestellung ohne customer_id
- leerer Rabattcode
- nachträglich korrigierter Meta-Spend
- Tag ohne Spend, Tag mit Spend ohne Bestellung
- 7-Tage-Werte

Einschränkung: Ohne Zeitzonen-Erweiterung rechnet DuckDB hier für die
Januar-Testdaten fest mit UTC+1. In BigQuery gilt DATE(created_at, 'Europe/Berlin'),
also inklusive Sommerzeit.

Ausführen:  pip install duckdb  &&  python check_logic_duckdb.py
"""

import duckdb

con = duckdb.connect()

# _dlt_load_id: ID des dlt Load Packages (Unix-Zeitstempel der Paketerstellung, als Text).
# Hier wird damit die neueste geladene Version ausgewählt.
con.execute("""
create table src_shopify_orders as select * from (values
 ('o1','c1', timestamp '2025-01-01 10:00:00', 50.0, null,      '1735797600.1'),
 ('o1','c1', timestamp '2025-01-01 10:00:00', 50.0, null,      '1735884000.1'),  -- doppelt geladen
 ('o2','c1', timestamp '2025-01-01 12:00:00', 30.0, null,      '1735797600.1'),  -- 2. Bestellung am ersten Tag
 ('o3','c2', timestamp '2025-01-01 23:30:00', 40.0, 'INFLU10', '1735797600.1'),  -- in Berlin schon 2. Januar
 ('o4','c1', timestamp '2025-01-03 09:00:00', 20.0, null,      '1735970400.1'),  -- Wiederkäufer
 ('o5',null, timestamp '2025-01-03 11:00:00', 25.0, '',        '1735970400.1')   -- Gast, leerer Code
) t(order_id, customer_id, created_at, total_price, discount_code, _dlt_load_id);

create table src_meta_insights as select * from (values
 (date '2025-01-01','k1', 40.0, 1000, 20, '1735797600.1'),
 (date '2025-01-01','k1', 45.0, 1100, 22, '1735884000.1'),  -- nachträglich korrigiert: 45 gilt
 (date '2025-01-02','k1', 30.0,  800, 15, '1735884000.1'),
 (date '2025-01-04','k1', 20.0,  500, 10, '1736056800.1')   -- Spend ohne Bestellung
) t("date", campaign_id, spend, impressions, clicks, _dlt_load_id);
""")

con.execute("""
create view stg_orders as
select order_id, customer_id,
       cast(created_at + interval 1 hour as date) as order_date,   -- BigQuery: DATE(created_at, 'Europe/Berlin')
       round(cast(total_price as decimal(18,2)), 2) as order_value_eur,
       nullif(trim(discount_code), '') as discount_code
from (select *, row_number() over (partition by order_id
                                   order by cast(_dlt_load_id as double) desc) rn
      from src_shopify_orders)
where rn = 1;

create view stg_meta as
select "date" as spend_date, campaign_id, round(cast(spend as decimal(18,2)), 2) spend_eur
from (select *, row_number() over (partition by "date", campaign_id
                                   order by cast(_dlt_load_id as double) desc) rn
      from src_meta_insights)
where rn = 1;

create view first_orders as
select customer_id, min(order_date) first_order_date
from stg_orders where customer_id is not null group by 1;

create view orders_daily as
select o.order_date, count(distinct o.order_id) orders, sum(o.order_value_eur) revenue_eur,
       count(distinct case when o.order_date = f.first_order_date then o.customer_id end) new_customers,
       count_if(o.customer_id is null) orders_without_customer,
       count_if(o.discount_code is not null) orders_with_discount
from stg_orders o left join first_orders f on o.customer_id = f.customer_id
group by 1;

create view meta_daily as select spend_date, sum(spend_eur) spend_eur from stg_meta group by 1;

create view daily as
select d.report_date,
  coalesce(s.spend_eur, 0) meta_spend_eur, coalesce(o.revenue_eur, 0) revenue_eur,
  coalesce(o.orders, 0) orders, coalesce(o.new_customers, 0) new_customers,
  coalesce(o.orders_with_discount, 0) orders_with_discount,
  coalesce(o.orders_without_customer, 0) orders_without_customer
from (select cast(range as date) report_date
      from range(date '2025-01-01', date '2025-01-05', interval 1 day)) d
left join meta_daily s on s.spend_date = d.report_date
left join orders_daily o on o.order_date = d.report_date;

create view fct as
select report_date, meta_spend_eur, revenue_eur, orders, new_customers,
  revenue_eur / nullif(meta_spend_eur, 0)                          blended_roas,
  meta_spend_eur / nullif(new_customers, 0)                        blended_cac_eur,
  sum(revenue_eur) over w / nullif(sum(meta_spend_eur) over w, 0)  blended_roas_7d,
  sum(meta_spend_eur) over w / nullif(sum(new_customers) over w, 0) blended_cac_7d_eur,
  orders_with_discount, orders_without_customer
from daily
window w as (order by report_date rows between 6 preceding and current row)
order by 1;
""")

rows = con.execute("select * from fct").fetchall()
cols = [d[0] for d in con.description]
result = {str(r[0]): dict(zip(cols, r)) for r in rows}


def r(value):
    return None if value is None else round(float(value), 4)


# Erwartungswerte pro Tag:
# (spend, umsatz, bestellungen, neukunden, roas, cac, roas_7d, cac_7d, rabatt, gast)
EXPECTED = {
    "2025-01-01": (45, 80, 2, 1, 1.7778, 45.0, 1.7778, 45.0, 0, 0),
    "2025-01-02": (30, 40, 1, 1, 1.3333, 30.0, 1.6,    37.5, 1, 0),
    "2025-01-03": (0,  45, 2, 0, None,   None, 2.2,    37.5, 0, 1),
    "2025-01-04": (20, 0,  0, 0, 0.0,    None, 1.7368, 47.5, 0, 0),
}
fields = ["meta_spend_eur", "revenue_eur", "orders", "new_customers", "blended_roas",
          "blended_cac_eur", "blended_roas_7d", "blended_cac_7d_eur",
          "orders_with_discount", "orders_without_customer"]

for day, expected in EXPECTED.items():
    actual = tuple(r(result[day][f]) for f in fields)
    ok = actual == tuple(r(v) for v in expected)
    print(f"{'OK ' if ok else 'FEHLER'}  {day}  {actual}")
    assert ok, f"{day}: erwartet {expected}"

print("Alle Erwartungswerte stimmen.")
