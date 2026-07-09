"""
FILE: experiment_mojibake.py
PURPOSE: One-off diagnostic script — NOT part of the pipeline. Tests ftfy
vs. a hand-rolled regex against real corrupted messages pulled from
raw_tickets, to decide how clean.py should handle the '???' artifact.
WHY THIS APPROACH: Rather than assuming ftfy (or a regex) would work,
this validates both against actual data first. Finding: '???' is a
Unicode replacement character, not mojibake — the original text is
genuinely unrecoverable, so normalization (not "repair") is the honest
framing used in clean.py.
INPUT: raw_tickets table (Postgres), filtered to rows containing '???'.
OUTPUT: printed comparison only — this script does not write anywhere.
"""

import os
import re
import psycopg2
import ftfy
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))


def manual_fix(text):
    """Revised: only target 3+ consecutive ? — the actual mojibake signature we found in Step 1, sparing legitimate '??' emphasis."""
    return re.sub(r"\?{3,}", "'", text)


def get_corrupted_samples(limit=15):
    """Pull real messages containing the ??? pattern directly from raw data."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticket_id, raw_json->'customer_messages' AS messages
            FROM raw_tickets
            WHERE raw_json::text LIKE %s
            LIMIT %s
            """,
            (
                "%???%",
                limit,
            ),
        )
        return cur.fetchall()


samples = get_corrupted_samples()
print(f"Found {len(samples)} sample tickets with ??? pattern.\n")

for ticket_id, messages in samples[:5]:  # just look at first 5 in detail
    text = messages[0] if messages else ""
    snippet = text[:200]  # first 200 chars is enough to judge

    print(f"--- {ticket_id} ---")
    print("ORIGINAL:", snippet)
    print("FTFY:    ", ftfy.fix_text(snippet))
    print("MANUAL:  ", manual_fix(snippet))
    print()

# Better metric: count remaining 3+ ? runs specifically, not any '?' at all
ftfy_fixed = sum(
    1 for _, m in samples if m and not re.search(r"\?{3,}", ftfy.fix_text(m[0]))
)
manual_fixed = sum(
    1 for _, m in samples if m and not re.search(r"\?{3,}", manual_fix(m[0]))
)
print(f"ftfy resolved {ftfy_fixed}/{len(samples)} samples (no more 3+ '?' runs)")
print(f"manual resolved {manual_fixed}/{len(samples)} samples (no more 3+ '?' runs)")
