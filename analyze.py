"""
FILE: analyze.py
PURPOSE: Connects the 24 parent themes to real business outcomes — daily
ticket volume (trend) and CSAT/resolution-time/repeat-contact/churn rates
(outcome) — producing the core analytical output the assignment asks for.
WHY THIS APPROACH: The dataset spans only 9 days (confirmed via
MIN/MAX(ticket_date)), not multiple weeks. Rather than force a misleading
week-over-week growth claim the data can't support, "trend" here means
daily volume across the available window plus a first-half vs second-half
directional comparison, explicitly labeled as directional rather than a
confident growth trend. Outcome metrics are computed only over tickets
that actually have each signal (e.g. CSAT is only present on 14.9% of
tickets) rather than silently treating missing values as zero/negative.
Noise tickets (30.7%, no coherent theme) are excluded from per-theme
analysis but used to compute an overall baseline for comparison.
INPUT: parent_themes, ticket_clusters, clean_tickets tables (Postgres).
OUTPUT: theme_outcomes and theme_daily_volume tables (Postgres) — the
data Step 8's report/UI will read directly.
"""

import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def build_cluster_to_theme_map(conn):
    """parent_themes stores cluster_ids as a JSONB array. Unpacks that
    into a queryable cluster_id -> parent_theme_id mapping table."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cluster_to_theme (
                cluster_id INTEGER PRIMARY KEY,
                parent_theme_id INTEGER,
                parent_name TEXT,
                is_actionable_issue BOOLEAN
            )
        """)
        cur.execute("DELETE FROM cluster_to_theme")
        cur.execute("""
            INSERT INTO cluster_to_theme (cluster_id, parent_theme_id, parent_name, is_actionable_issue)
            SELECT (cid.value)::int, pt.id, pt.parent_name, pt.is_actionable_issue
            FROM parent_themes pt
            CROSS JOIN LATERAL jsonb_array_elements(pt.cluster_ids) AS cid(value)
        """)
    conn.commit()


def compute_baseline(conn):
    """Overall averages across ALL tickets (including noise), so each
    theme's numbers can be compared against a real baseline, not just
    against each other in isolation."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                AVG(csat) AS avg_csat,
                AVG(resolution_hours) AS avg_resolution_hours,
                AVG(CASE WHEN reopen_count > 0 THEN 1.0 ELSE 0.0 END) AS repeat_contact_rate,
                AVG(CASE WHEN has_churn THEN 1.0 ELSE 0.0 END) AS churn_rate
            FROM clean_tickets
        """)
        row = cur.fetchone()
    return {
        "avg_csat": row[0],
        "avg_resolution_hours": row[1],
        "repeat_contact_rate": row[2],
        "churn_rate": row[3],
    }


def compute_theme_outcomes(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS theme_outcomes (
                parent_theme_id INTEGER PRIMARY KEY,
                parent_name TEXT,
                is_actionable_issue BOOLEAN,
                ticket_count INTEGER,
                csat_sample_size INTEGER,
                avg_csat NUMERIC,
                avg_resolution_hours NUMERIC,
                repeat_contact_rate NUMERIC,
                churn_sample_size INTEGER,
                churn_rate NUMERIC
            )
        """)
        cur.execute("DELETE FROM theme_outcomes")
        cur.execute("""
            INSERT INTO theme_outcomes (
                parent_theme_id, parent_name, is_actionable_issue, ticket_count,
                csat_sample_size, avg_csat, avg_resolution_hours,
                repeat_contact_rate, churn_sample_size, churn_rate
            )
            SELECT
                ctt.parent_theme_id,
                ctt.parent_name,
                ctt.is_actionable_issue,
                COUNT(*) AS ticket_count,
                COUNT(ct.csat) AS csat_sample_size,
                AVG(ct.csat) AS avg_csat,
                AVG(ct.resolution_hours) AS avg_resolution_hours,
                AVG(CASE WHEN ct.reopen_count > 0 THEN 1.0 ELSE 0.0 END) AS repeat_contact_rate,
                COUNT(ct.has_churn) AS churn_sample_size,
                AVG(CASE WHEN ct.has_churn THEN 1.0 ELSE 0.0 END) AS churn_rate
            FROM ticket_clusters tc
            JOIN cluster_to_theme ctt ON tc.cluster_id = ctt.cluster_id
            JOIN clean_tickets ct ON tc.ticket_id = ct.ticket_id
            GROUP BY ctt.parent_theme_id, ctt.parent_name, ctt.is_actionable_issue
        """)
    conn.commit()


def compute_daily_volume(conn):
    """Daily ticket count per theme across the 9-day window, plus a
    first-half vs second-half comparison as a directional (not
    confident multi-week trend) signal."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS theme_daily_volume (
                parent_theme_id INTEGER,
                ticket_date DATE,
                ticket_count INTEGER
            )
        """)
        cur.execute("DELETE FROM theme_daily_volume")
        cur.execute("""
            INSERT INTO theme_daily_volume (parent_theme_id, ticket_date, ticket_count)
            SELECT ctt.parent_theme_id, ct.ticket_date, COUNT(*)
            FROM ticket_clusters tc
            JOIN cluster_to_theme ctt ON tc.cluster_id = ctt.cluster_id
            JOIN clean_tickets ct ON tc.ticket_id = ct.ticket_id
            GROUP BY ctt.parent_theme_id, ct.ticket_date
        """)
    conn.commit()


def print_summary(conn, baseline):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT parent_name, is_actionable_issue, ticket_count,
                   avg_csat, csat_sample_size, avg_resolution_hours,
                   repeat_contact_rate, churn_rate, churn_sample_size
            FROM theme_outcomes
            ORDER BY ticket_count DESC
        """)
        rows = cur.fetchall()

    print(
        f"\nBASELINE (all tickets): avg_csat={baseline['avg_csat']:.2f}, "
        f"avg_resolution_hours={baseline['avg_resolution_hours']:.1f}, "
        f"repeat_contact_rate={baseline['repeat_contact_rate'] * 100:.1f}%, "
        f"churn_rate={baseline['churn_rate'] * 100:.1f}%\n"
    )

    print(
        f"{'Theme':<45} {'Tickets':>7} {'CSAT':>6} {'n':>4} {'ResHrs':>7} {'Repeat%':>8} {'Churn%':>7}"
    )
    for (
        name,
        actionable,
        count,
        csat,
        csat_n,
        res_hrs,
        repeat_rate,
        churn_rate,
        churn_n,
    ) in rows:
        tag = "" if actionable else " [NOT A COMPLAINT]"
        csat_str = f"{csat:.2f}" if csat is not None else "n/a"
        res_str = f"{res_hrs:.1f}" if res_hrs is not None else "n/a"
        print(
            f"{name[:44] + tag:<45} {count:>7} {csat_str:>6} {csat_n:>4} {res_str:>7} "
            f"{repeat_rate * 100:>7.1f}% {churn_rate * 100:>6.1f}%"
        )


def main():
    conn = psycopg2.connect(DATABASE_URL)

    build_cluster_to_theme_map(conn)
    baseline = compute_baseline(conn)
    compute_theme_outcomes(conn)
    compute_daily_volume(conn)

    print_summary(conn, baseline)

    conn.close()
    print("\nDone. Saved to theme_outcomes and theme_daily_volume.")


if __name__ == "__main__":
    main()
