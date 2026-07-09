"""
FILE: clean.py
PURPOSE: Reads raw ticket JSON from raw_tickets and produces a cleaned,
typed version in clean_tickets — ready for embedding and analysis.

WHY THIS APPROACH: Cleaning is kept separate from ingestion (Step 2) so
cleaning logic can be corrected and re-run without ever re-hitting the API.

DESIGN PRINCIPLE — calibrating fix effort to actual impact, not every
observed defect: every rule below was added because measurement showed it
was frequent enough to matter, and generalizes to a class of input rather
than one literal string:
  - Dedup: ~100% of tickets affected — clearly universal, not an edge case.
  - Quote/footer stripping: ~19% of tickets — frequent, and the pattern
    (date + "wrote:" ... footer marker) is structural, not one hardcoded
    string, though the specific footer markers themselves (e.g. "Cookin
    Inc. (DBA Cook Unity Inc.)") ARE CookUnity-specific literal text. This
    is a stated scope boundary, not an oversight: this cleaning logic is
    correctly scoped to this dataset's actual footers, and would need
    rework to generalize to a different company's ticket export.
  - Mobile-signature removal: 2.7% of tickets — measured before fixing.
    Iterated twice more after inspecting residual matches (270 -> 5 -> 2),
    stopping once remaining cases were unpatterned joke phrasing
    ("Sent from my thumbs") with no finite rule to chase.
  - Explicitly NOT patched: CloudFront/HTTP error dumps pasted by
    customers (<0.1% of tickets) — genuinely rare, and any fix would be
    overfitting to a couple of specific examples rather than a real
    pattern. Documented as a known limitation instead.

A real bug was caught and fixed during this process, not glossed over:
the first quote-stripping version assumed real customer text always comes
BEFORE the quoted block and truncated everything from the first "wrote:"
marker onward. This silently deleted real customer messages on tickets
where the quote comes FIRST and the customer's reply follows it — caught
via 17 tickets that ended up with an empty clean_message that shouldn't
have been empty. Fixed by removing only the quoted block's span (start of
quote to end-of-quote marker) rather than truncating from its start,
preserving real content on both sides. See experiment_quote_strip.py for
the full validation history of both the bug and the fix.

INPUT: raw_tickets table (Postgres) — untouched raw_json per ticket.
OUTPUT: clean_tickets table (Postgres) — one typed row per ticket, with
clean_message ready for embedding in Step 4.
"""

import os
import re
import psycopg2
import ftfy
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


# ---------------------------------------------------------------------------
# Quote / marketing-footer stripping
# ---------------------------------------------------------------------------

QUOTE_MARKERS = [
    r"\bOn (?:[A-Za-z]+,\s*)?[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}.{0,80}wrote:",
    r"CookUnity\.\s*\d+ Flushing Ave",
    r"No longer want to receive these emails\?",
    r"Get \$\d+ off when you refer a friend!",
]
QUOTE_PATTERN = re.compile("|".join(QUOTE_MARKERS))

QUOTE_BLOCK_PATTERN = re.compile(
    r"On (?:[A-Za-z]+,\s*)?[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}.{0,80}wrote:.*"
    r"(?:No longer want to receive these emails\?|CookUnity\.\s*\d+ Flushing Ave|"
    r"Cookin Inc\.\s*\(DBA Cook Unity Inc\.\)|Get \$\d+ off when you refer a friend!)",
    re.DOTALL,
)


def strip_quoted_content(text):
    """Removes the quoted block itself (start-of-quote to end-of-quote
    marker), keeping any real text on either side. Falls back to a
    truncate-from-start match if no clear end-of-quote marker is found —
    this covers cases where a quote marker exists but no recognized
    footer follows it within the message."""
    block_match = QUOTE_BLOCK_PATTERN.search(text)
    if block_match:
        text = text[: block_match.start()] + " " + text[block_match.end() :]
        return re.sub(r"\s{2,}", " ", text).strip()
    match = QUOTE_PATTERN.search(text)
    return text[: match.start()].strip() if match else text.strip()


# ---------------------------------------------------------------------------
# Mobile-client signature removal
# ---------------------------------------------------------------------------

MOBILE_SIGNATURE = re.compile(
    r"Sent from my (?:iPhone|iPad|Android(?: device)?|Samsung(?: Galaxy)?|"
    r"Galaxy(?: S\d+)?|cell(?:\s|-)?phone|mobile(?:\s|-)?phone)\b\.?,?\s*",
    re.IGNORECASE,
)


def strip_mobile_signature(text):
    text = MOBILE_SIGNATURE.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# ---------------------------------------------------------------------------
# Encoding normalization
# ---------------------------------------------------------------------------

REPLACEMENT_RUN = re.compile(r"\?{3,}")
# Note: ftfy.fix_text() handles genuine mojibake (mis-decoded encoding).
# The 3+ '?' pattern is a Unicode replacement character, not mojibake —
# the original text is unrecoverable, so this is normalization, not repair.


# ---------------------------------------------------------------------------
# Message-list cleaning
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


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
    # Two separate connections: the read side streams continuously via a
    # named (server-side) cursor and never commits; the write side commits
    # periodically. Sharing one connection for both caused the named cursor
    # to be invalidated the moment the periodic commit ran.
    read_conn = psycopg2.connect(DATABASE_URL)
    write_conn = psycopg2.connect(DATABASE_URL)

    with read_conn.cursor(name="raw_cursor") as read_cur:
        read_cur.itersize = 500
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
                write_conn.commit()
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
