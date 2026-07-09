"""
FILE: clean.py
PURPOSE: Reads raw ticket JSON from raw_tickets and produces a cleaned,
typed version in clean_tickets — ready for embedding and analysis.
WHY THIS APPROACH: Cleaning is kept separate from ingestion (Step 2) so
cleaning logic can be corrected and re-run without ever re-hitting the API.
Each transformation (dedupe, quote-stripping, mobile-signature removal,
encoding fix) was validated against real corrupted samples in
experiment_mojibake.py and experiment_quote_strip.py before being
included here — see those files for the evidence behind each decision.
INPUT: raw_tickets table (Postgres) — untouched raw_json per ticket.
OUTPUT: clean_tickets table (Postgres) — one typed row per ticket, with
clean_message ready for embedding in Step 4.
"""

import os
import re
import psycopg2
import psycopg2.extras
import ftfy
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

QUOTE_MARKERS = [
    r"\bOn (?:[A-Za-z]+,\s*)?[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}.{0,80}wrote:",
    r"CookUnity\.\s*\d+ Flushing Ave",
    r"No longer want to receive these emails\?",
    r"Get \$\d+ off when you refer a friend!",
]
QUOTE_PATTERN = re.compile("|".join(QUOTE_MARKERS))
REPLACEMENT_RUN = re.compile(r"\?{3,}")

MOBILE_SIGNATURE = re.compile(
    r"Sent from my (?:iPhone|iPad|Android(?: device)?|Samsung(?: Galaxy)?|Galaxy(?: S\d+)?|cell(?:\s|-)?phone|mobile(?:\s|-)?phone)\b\.?,?\s*",
    re.IGNORECASE,
)


def strip_mobile_signature(text):
    text = MOBILE_SIGNATURE.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def strip_quoted_content(text):
    match = QUOTE_PATTERN.search(text)
    return text[: match.start()].strip() if match else text.strip()


def dedupe_preserve_order(messages):
    seen = set()
    result = []
    for m in messages:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def clean_message_block(raw_messages):
    """Returns (clean_text, was_deduped, was_quote_stripped)."""
    if not raw_messages:
        return None, False, False

    deduped = dedupe_preserve_order(raw_messages)
    was_deduped = len(deduped) < len(raw_messages)

    stripped = [strip_quoted_content(m) for m in deduped]
    was_quote_stripped = any(len(s) < len(orig) for s, orig in zip(stripped, deduped))

    stripped = [strip_mobile_signature(m) for m in stripped]

    joined = " ".join(s for s in stripped if s)
    fixed = ftfy.fix_text(joined)
    fixed = REPLACEMENT_RUN.sub("'", fixed)

    return fixed, was_deduped, was_quote_stripped


def create_clean_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clean_tickets (
                ticket_id TEXT PRIMARY KEY,
                ticket_date DATE,
                channel TEXT,
                status TEXT,
                main_contact_reason TEXT,
                contact_reason TEXT,
                region TEXT,
                has_churn BOOLEAN,          -- nullable: NULL = unknown, not false
                csat INTEGER,
                response_csat TEXT,
                first_response_minutes INTEGER,
                resolution_hours NUMERIC,
                message_count INTEGER,
                customer_message_count INTEGER,
                reopen_count INTEGER,
                clean_message TEXT,
                raw_message_count INTEGER,
                was_deduped BOOLEAN,
                was_quote_stripped BOOLEAN
            )
        """)
    conn.commit()


def process_all():
    read_conn = psycopg2.connect(DATABASE_URL)
    write_conn = psycopg2.connect(DATABASE_URL)

    with read_conn.cursor(name="raw_cursor") as read_cur:
        read_cur.itersize = 500  # fetch 500 rows at a time from the server
        read_cur.execute("SELECT raw_json FROM raw_tickets")

        write_cur = write_conn.cursor()
        processed = 0

        for (raw,) in read_cur:
            raw_messages = raw.get("customer_messages") or []
            clean_text, was_deduped, was_quote_stripped = clean_message_block(
                raw_messages
            )

            write_cur.execute(
                """
                INSERT INTO clean_tickets (
                    ticket_id, ticket_date, channel, status, main_contact_reason,
                    contact_reason, region, has_churn, csat, response_csat,
                    first_response_minutes, resolution_hours, message_count,
                    customer_message_count, reopen_count, clean_message,
                    raw_message_count, was_deduped, was_quote_stripped
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ticket_id) DO NOTHING
                """,
                (
                    raw.get("ticket_id"),
                    raw.get("ticket_date"),
                    raw.get("channel"),
                    raw.get("status"),
                    raw.get("main_contact_reason"),
                    raw.get("contact_reason"),
                    raw.get("region"),
                    raw.get("has_churn"),
                    raw.get("csat"),
                    raw.get("response_csat"),
                    raw.get("first_response_minutes"),
                    raw.get("resolution_hours"),
                    raw.get("message_count"),
                    raw.get("customer_message_count"),
                    raw.get("reopen_count"),
                    clean_text,
                    len(raw_messages),
                    was_deduped,
                    was_quote_stripped,
                ),
            )
            processed += 1
            if processed % 1000 == 0:
                write_conn.commit()  # only commits on write_conn now — read_conn is untouched
                print(f"  ...processed {processed}")

        write_conn.commit()

    read_conn.close()
    write_conn.close()
    return processed


def main():
    setup_conn = psycopg2.connect(DATABASE_URL)
    create_clean_table(setup_conn)
    setup_conn.close()

    total = process_all()
    print(f"Done. Cleaned {total} tickets into clean_tickets.")


if __name__ == "__main__":
    main()
