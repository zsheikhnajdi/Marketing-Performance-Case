"""
Führt den echten Prefect-Flow von Anfang bis Ende aus.
Nur die beiden externen Systeme werden simuliert:
BigQuery liefert eine vorbereitete Zeile, Slack wird abgefangen statt gesendet.

Ausführen:  pip install -r automation/requirements.txt
            python automation/test_flow_mocked.py
"""

import os
from decimal import Decimal
from unittest import mock

os.environ.setdefault("PREFECT_LOGGING_LEVEL", "WARNING")

from google.cloud.bigquery.table import Row  # noqa: E402

import roas_alert_flow as flow_module  # noqa: E402

FIELDS = ["report_date", "meta_spend_eur", "revenue_eur", "orders",
          "new_customers", "blended_roas", "blended_cac_eur"]


def fake_bigquery(values):
    rows = [] if values is None else [Row(values, {k: i for i, k in enumerate(FIELDS)})]
    client = mock.MagicMock()
    client.query.return_value.result.return_value = rows
    return client


SCENARIOS = [
    ("ROAS 1,2: Alert",
     ("2026-09-20", Decimal("1234.50"), Decimal("1481.40"), 21, 17, Decimal("1.2"), Decimal("72.62")),
     "ROAS-Warnung"),
    ("ROAS 2,8: kein Alert",
     ("2026-09-20", Decimal("500"), Decimal("1400"), 30, 12, Decimal("2.8"), Decimal("41.67")),
     None),
    ("Spend ohne Bestellung",
     ("2026-09-20", Decimal("200"), Decimal("0"), 0, 0, Decimal("0"), None),
     "keine einzige Bestellung"),
    ("kein Spend",
     ("2026-09-20", Decimal("0"), Decimal("300"), 8, 3, None, Decimal("0")),
     None),
    ("keine Zeile für gestern",
     None,
     "keine Zeile"),
]

for name, values, expected in SCENARIOS:
    sent = []

    def fake_post(url, json, timeout):
        sent.append(json)
        response = mock.MagicMock()
        response.raise_for_status.return_value = None
        return response

    secret = mock.MagicMock()
    secret.get.return_value = "https://hooks.slack.test/example"

    with mock.patch.object(flow_module.bigquery, "Client", return_value=fake_bigquery(values)), \
         mock.patch.object(flow_module.requests, "post", side_effect=fake_post), \
         mock.patch.object(flow_module.Secret, "load", return_value=secret):
        flow_module.daily_roas_alert()

    text = sent[0]["text"] if sent else None
    passed = (text is None) if expected is None else (text is not None and expected in text)
    print(f"{'OK ' if passed else 'FEHLER'}  {name:26s} -> {text or '(nichts gesendet)'}")
    assert passed

print("Flow-Test bestanden.")
