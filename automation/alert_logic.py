"""
Entscheidungs- und Nachrichtenlogik für den ROAS-Alert.

Bewusst ohne Abhängigkeiten zu Prefect, BigQuery oder Slack.
Dadurch lässt sich die Logik direkt importieren und testen.
"""


def decide_action(row: dict | None, threshold: float) -> str:
    """Gibt zurück, was mit den Werten von gestern passieren soll."""

    if row is None:
        # Die Tabelle hat für jeden Tag eine Zeile. Fehlt gestern, ist dbt nicht gelaufen.
        return "missing_data"

    if row["blended_roas"] is None:
        # Kein Meta-Spend gestern: ROAS ist nicht definiert, also kein Alert.
        return "no_action"

    if row["meta_spend_eur"] > 0 and row["orders"] == 0:
        # Spend ohne eine einzige Bestellung kann auf einen Ladefehler bei Shopify
        # oder auf ein Problem im Shop, zum Beispiel beim Checkout, hindeuten.
        # Beides soll auffallen, aber nicht als ROAS-Einbruch gemeldet werden.
        return "data_warning"

    if float(row["blended_roas"]) < threshold:
        return "roas_alert"

    return "no_action"


def num(value, digits: int = 2) -> str:
    """Zahl im deutschen Format, z. B. 1.234,56"""
    formatted = f"{float(value):,.{digits}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def eur(value) -> str:
    return "–" if value is None else f"{num(value)} €"


def roas_alert_message(row: dict, threshold: float) -> dict:
    roas = float(row["blended_roas"])
    return {
        # Kurzer Text für Benachrichtigungen auf dem Handy
        "text": f"ROAS-Warnung: {num(roas)} am {row['report_date']}",
        "blocks": [
            {"type": "header",
             "text": {"type": "plain_text", "text": "ROAS unter der Schwelle"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Datum*\n{row['report_date']}"},
                {"type": "mrkdwn", "text": f"*Blended ROAS*\n{num(roas)} (Schwelle {num(threshold, 1)})"},
                {"type": "mrkdwn", "text": f"*Meta-Spend*\n{eur(row['meta_spend_eur'])}"},
                {"type": "mrkdwn", "text": f"*Umsatz*\n{eur(row['revenue_eur'])}"},
                {"type": "mrkdwn", "text": f"*Neukunden*\n{row['new_customers']}"},
                {"type": "mrkdwn", "text": f"*CAC*\n{eur(row['blended_cac_eur'])}"},
            ]},
            {"type": "context", "elements": [
                {"type": "mrkdwn",
                 "text": "Blended ROAS = Gesamtumsatz / Meta-Spend. "
                         "Nicht der ROAS aus dem Meta Ads Manager."}
            ]},
        ],
    }


def data_warning_message(row: dict) -> dict:
    return {
        "text": (
            f":warning: Bitte prüfen: Am {row['report_date']} gab es Meta-Spend von "
            f"{eur(row['meta_spend_eur'])}, aber keine einzige Bestellung. "
            "Möglich sind ein Ladefehler bei Shopify oder ein Problem im Shop, "
            "zum Beispiel beim Checkout. Es wurde kein ROAS-Alert gesendet."
        )
    }


MISSING_DATA_MESSAGE = {
    "text": ":warning: Für gestern gibt es keine Zeile in fct_marketing_performance. "
            "Bitte die Pipeline prüfen."
}
