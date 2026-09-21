"""Tests der Entscheidungs- und Nachrichtenlogik, ohne BigQuery und ohne Slack."""

from decimal import Decimal

from alert_logic import data_warning_message, decide_action, roas_alert_message


def row(spend, orders, roas):
    return {"report_date": "2026-09-20", "meta_spend_eur": Decimal(spend), "orders": orders,
            "revenue_eur": Decimal("0"), "new_customers": 0, "blended_cac_eur": None,
            "blended_roas": None if roas is None else Decimal(roas)}


CASES = [
    ("keine Zeile für gestern",  None,                  "missing_data"),
    ("kein Spend gestern",       row("0", 5, None),     "no_action"),
    ("Spend ohne Bestellungen",  row("200", 0, "0"),    "data_warning"),
    ("ROAS unter 1,5",           row("200", 3, "1.2"),  "roas_alert"),
    ("ROAS genau 1,5",           row("200", 4, "1.5"),  "no_action"),
    ("ROAS über 1,5",            row("200", 9, "2.8"),  "no_action"),
]

for name, data, expected in CASES:
    result = decide_action(data, 1.5)
    print(f"{'OK ' if result == expected else 'FEHLER'}  {name:26s} -> {result}")
    assert result == expected

# Nachrichten: deutsches Zahlenformat und klare Kennzeichnung
alert = roas_alert_message(row("1234.5", 3, "1.2"), 1.5)
assert alert["text"] == "ROAS-Warnung: 1,20 am 2026-09-20"
assert "1.234,50 €" in str(alert["blocks"])
assert "Blended ROAS" in str(alert["blocks"])
assert "keine einzige Bestellung" in data_warning_message(row("200", 0, "0"))["text"]
print("OK   Nachrichtenformat")

print("Alle Tests bestanden.")
