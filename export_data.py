"""
FILE: export_data.py
PURPOSE: Exports the finished theme_outcomes, theme_daily_volume,
cluster_labels, and baseline data into a single static JSON file for the
Next.js frontend to consume at build time.
WHY THIS APPROACH: The Next.js app will be deployed to Vercel, which
cannot reach a Postgres database running in a local Docker container.
Rather than standing up a hosted database just to serve a point-in-time
snapshot report, this exports the data ONCE into a static JSON file that
gets committed to the frontend repo and read at build time (no live DB
connection at runtime at all). This is the same "point-in-time snapshot,
not a live dashboard" reasoning already used elsewhere in this project.
INPUT: theme_outcomes, theme_daily_volume, cluster_labels, cluster_to_theme,
clean_tickets tables (Postgres).
OUTPUT: report-data.json — a single file containing everything the
frontend needs, with no further database access required.
"""

import os
import json
import psycopg2
from decimal import Decimal
from datetime import date
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def to_jsonable(value):
    """Postgres NUMERIC columns come back as Decimal (not JSON-serializable)
    and DATE columns come back as datetime.date objects (also not
    JSON-serializable) — convert both to plain JSON-friendly types."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def fetch_all_data(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT parent_theme_id, parent_name, is_actionable_issue, ticket_count,
                   avg_csat, csat_sample_size, avg_resolution_hours,
                   repeat_contact_rate, churn_rate, churn_sample_size
            FROM theme_outcomes
            ORDER BY ticket_count DESC
        """)
        theme_rows = cur.fetchall()

        cur.execute("""
            SELECT AVG(csat), AVG(resolution_hours),
                   AVG(CASE WHEN reopen_count > 0 THEN 1.0 ELSE 0.0 END),
                   AVG(CASE WHEN has_churn THEN 1.0 ELSE 0.0 END)
            FROM clean_tickets
        """)
        baseline_row = cur.fetchone()

        cur.execute("""
            SELECT parent_theme_id, ticket_date, ticket_count
            FROM theme_daily_volume
            ORDER BY parent_theme_id, ticket_date
        """)
        daily_rows = cur.fetchall()

        cur.execute("""
            SELECT ctt.parent_theme_id, cl.evidence_quotes
            FROM cluster_labels cl
            JOIN cluster_to_theme ctt ON cl.cluster_id = ctt.cluster_id
            WHERE cl.cluster_id != -1
        """)
        evidence_rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM ticket_clusters WHERE cluster_id = -1")
        noise_count = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM clean_tickets
            WHERE clean_message IS NULL OR clean_message = ''
        """)
        empty_count = cur.fetchone()[0]

    return theme_rows, baseline_row, daily_rows, evidence_rows, noise_count, empty_count


def build_export(
    theme_rows, baseline_row, daily_rows, evidence_rows, noise_count, empty_count
):
    # Group evidence quotes by theme (a theme can merge multiple clusters,
    # so multiple rows may contribute quotes to the same theme_id).
    evidence_by_theme = {}
    for theme_id, quotes_json in evidence_rows:
        quotes = (
            quotes_json if isinstance(quotes_json, list) else json.loads(quotes_json)
        )
        evidence_by_theme.setdefault(theme_id, []).extend(quotes)

    # Group daily volume by theme, as a list of {date, count} — the
    # frontend renders this directly as a sparkline, no reshaping needed.
    daily_by_theme = {}
    for theme_id, ticket_date, count in daily_rows:
        daily_by_theme.setdefault(theme_id, []).append(
            {
                "date": to_jsonable(ticket_date),
                "count": count,
            }
        )

    themes = []
    for row in theme_rows:
        (
            theme_id,
            name,
            is_actionable,
            ticket_count,
            avg_csat,
            csat_n,
            avg_resolution_hours,
            repeat_rate,
            churn_rate,
            churn_n,
        ) = row
        themes.append(
            {
                "id": theme_id,
                "name": name,
                "isActionable": is_actionable,
                "ticketCount": ticket_count,
                "avgCsat": to_jsonable(avg_csat),
                "csatSampleSize": csat_n,
                "avgResolutionHours": to_jsonable(avg_resolution_hours),
                "repeatContactRate": to_jsonable(repeat_rate),
                "churnRate": to_jsonable(churn_rate),
                "churnSampleSize": churn_n,
                "evidenceQuotes": evidence_by_theme.get(theme_id, []),
                "dailyVolume": daily_by_theme.get(theme_id, []),
            }
        )

    avg_csat_b, avg_res_b, repeat_b, churn_b = baseline_row

    return {
        "generatedAt": None,  # filled in by main() at write time
        "dateRange": {"start": "2026-04-23", "end": "2026-05-01"},
        "baseline": {
            "avgCsat": to_jsonable(avg_csat_b),
            "avgResolutionHours": to_jsonable(avg_res_b),
            "repeatContactRate": to_jsonable(repeat_b),
            "churnRate": to_jsonable(churn_b),
        },
        "themes": themes,
        "noiseCount": noise_count,
        "emptyMessageCount": empty_count,
    }


def main():
    conn = psycopg2.connect(DATABASE_URL)
    theme_rows, baseline_row, daily_rows, evidence_rows, noise_count, empty_count = (
        fetch_all_data(conn)
    )
    conn.close()

    export = build_export(
        theme_rows, baseline_row, daily_rows, evidence_rows, noise_count, empty_count
    )

    from datetime import datetime

    export["generatedAt"] = datetime.now().isoformat()

    with open("report-data.json", "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2)

    actionable_count = sum(1 for t in export["themes"] if t["isActionable"])
    print(
        f"Done. Wrote report-data.json ({len(export['themes'])} themes, {actionable_count} actionable)."
    )


if __name__ == "__main__":
    main()
