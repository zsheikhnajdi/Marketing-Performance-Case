"""
Täglicher ROAS-Check als Prefect-Flow.

Reihenfolge in der täglichen Pipeline:
    1. dlt lädt Shopify und Meta
    2. dbt source freshness   bricht ab, wenn eine Quelle zu alt ist
    3. dbt build              Modelle und Tests
    4. dieser Flow            ROAS-Check und Slack

Zeitplan: Prefect Deployment mit Cron, z. B. täglich 06:30 Uhr.

Konfiguration:
    ROAS_THRESHOLD   Schwelle für den Alert (Standard: 1.5)
    FCT_TABLE        BigQuery-Tabelle mit den Tageswerten
    Slack-Webhook    als Prefect Secret Block "slack-webhook-marketing"
"""

import os

import requests
from google.cloud import bigquery
from prefect import flow, get_run_logger, task
from prefect.blocks.system import Secret

from alert_logic import (
    MISSING_DATA_MESSAGE,
    data_warning_message,
    decide_action,
    roas_alert_message,
)

ROAS_THRESHOLD = float(os.getenv("ROAS_THRESHOLD", "1.5"))

# dbt legt das Dataset als <Ziel-Dataset>_marts an, z. B. analytics_marts.
FCT_TABLE = os.getenv("FCT_TABLE", "analytics_marts.fct_marketing_performance")

QUERY = f"""
    select
        report_date,
        meta_spend_eur,
        revenue_eur,
        orders,
        new_customers,
        blended_roas,
        blended_cac_eur
    from `{FCT_TABLE}`
    where report_date = date_sub(current_date('Europe/Berlin'), interval 1 day)
"""


@task(retries=2, retry_delay_seconds=300)
def fetch_yesterday() -> dict | None:
    client = bigquery.Client()
    rows = list(client.query(QUERY).result())
    return dict(rows[0].items()) if rows else None


@task(retries=3, retry_delay_seconds=60)
def send_to_slack(payload: dict) -> None:
    webhook_url = Secret.load("slack-webhook-marketing").get()
    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


@flow(name="daily-roas-alert")
def daily_roas_alert() -> None:
    logger = get_run_logger()
    row = fetch_yesterday()
    action = decide_action(row, ROAS_THRESHOLD)

    if action == "missing_data":
        send_to_slack(MISSING_DATA_MESSAGE)
    elif action == "data_warning":
        send_to_slack(data_warning_message(row))
    elif action == "roas_alert":
        send_to_slack(roas_alert_message(row, ROAS_THRESHOLD))
    else:
        logger.info("Kein Alert nötig.")


if __name__ == "__main__":
    daily_roas_alert()
