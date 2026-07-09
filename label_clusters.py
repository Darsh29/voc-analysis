"""
FILE: label_clusters.py
PURPOSE: Uses Claude to name each cluster's theme and extract grounded
evidence quotes, from raw ticket text only — the existing
contact_reason/main_contact_reason labels are deliberately NOT shown to
Claude during this step, so theme discovery is independent rather than
just echoing back an existing (and per /meta, possibly noisy) category.
The comparison against existing labels happens separately, afterward.
WHY THIS APPROACH: Clustering (Step 5) already did the cheap, deterministic
grouping. This step needs actual judgment — turning "cluster 10, 475
tickets" into a human-readable theme name a support lead could act on.
Model is claude-sonnet-5, not a cheaper/smaller model — with only 32
calls total, cost is negligible either way, so quality was prioritized
since these labels are the most customer-facing output of the project.
Evidence quotes are verified against the source text after generation
(not just trusted) — any quote that doesn't actually appear in what was
shown to Claude is flagged rather than silently stored, keeping this
step checkable by a human reviewer rather than taking model output on faith.
INPUT: ticket_clusters + clean_tickets tables (Postgres).
OUTPUT: cluster_labels table (Postgres) — one row per real cluster
(noise/-1 is labeled directly as "Uncategorized", no API call needed).
"""

import os
import json
import random
import time
import psycopg2
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL = "claude-sonnet-5"
SAMPLE_SIZE = 15
RANDOM_SEED = 42

client = Anthropic()  # reads ANTHROPIC_API_KEY from env automatically


def get_clusters(conn):
    """Returns list of (cluster_id, ticket_count) for real clusters, excluding noise."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cluster_id, COUNT(*) as cnt
            FROM ticket_clusters
            WHERE cluster_id != -1
            GROUP BY cluster_id
            ORDER BY cluster_id
        """)
        return cur.fetchall()


def sample_messages(conn, cluster_id, sample_size=SAMPLE_SIZE):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ct.ticket_id, ct.clean_message
            FROM ticket_clusters tc
            JOIN clean_tickets ct ON tc.ticket_id = ct.ticket_id
            WHERE tc.cluster_id = %s AND ct.clean_message IS NOT NULL
        """,
            (cluster_id,),
        )
        rows = cur.fetchall()

    random.seed(RANDOM_SEED)
    if len(rows) > sample_size:
        rows = random.sample(rows, sample_size)
    return rows


def build_prompt(messages):
    numbered = "\n\n".join(f"[{i + 1}] {msg}" for i, (_, msg) in enumerate(messages))
    return f"""Below are {len(messages)} real customer support messages that an algorithm grouped together as similar. Your job is to identify the common theme.

{numbered}

Respond with ONLY a JSON object (no markdown fences, no preamble) in this exact shape:
{{
  "theme_name": "a short, specific, human-readable name for this theme (5-8 words)",
  "description": "1-2 sentences describing what this theme actually is",
  "evidence_quotes": ["a short verbatim excerpt from one of the messages above, max 20 words", "a second verbatim excerpt from a DIFFERENT message, max 20 words"]
}}

The evidence_quotes MUST be exact substrings copied from the messages above — do not paraphrase or invent them."""


def label_cluster(messages, retries=3):
    prompt = build_prompt(messages)
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            text = (
                text.removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return json.loads(text)
        except Exception as e:
            wait = 2**attempt
            print(f"  Labeling call failed ({e}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Failed to label cluster after all retries")


def verify_quotes(quotes, messages):
    """Checks each quote actually appears in the source text shown to Claude.
    Returns (verified_quotes, unverified_quotes) — doesn't silently drop
    unverified ones, so a human can review what didn't check out."""
    full_text = " ".join(msg for _, msg in messages).lower()
    verified, unverified = [], []
    for q in quotes:
        if q.lower().strip() in full_text:
            verified.append(q)
        else:
            unverified.append(q)
    return verified, unverified


def save_label(conn, cluster_id, ticket_count, sample_size, result, unverified):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cluster_labels (
                cluster_id INTEGER PRIMARY KEY,
                theme_name TEXT,
                description TEXT,
                evidence_quotes JSONB,
                unverified_quotes JSONB,
                ticket_count INTEGER,
                sample_size INTEGER
            )
        """)
        cur.execute(
            """
            INSERT INTO cluster_labels (cluster_id, theme_name, description, evidence_quotes, unverified_quotes, ticket_count, sample_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cluster_id) DO UPDATE SET
                theme_name = EXCLUDED.theme_name,
                description = EXCLUDED.description,
                evidence_quotes = EXCLUDED.evidence_quotes,
                unverified_quotes = EXCLUDED.unverified_quotes
        """,
            (
                cluster_id,
                result["theme_name"],
                result["description"],
                json.dumps(result["evidence_quotes"]),
                json.dumps(unverified),
                ticket_count,
                sample_size,
            ),
        )
    conn.commit()


def label_noise(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ticket_clusters WHERE cluster_id = -1")
        count = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO cluster_labels (cluster_id, theme_name, description, evidence_quotes, unverified_quotes, ticket_count, sample_size)
            VALUES (-1, 'Uncategorized', 'Tickets that did not cluster into any coherent theme — one-off or highly individual issues.', '[]', '[]', %s, 0)
            ON CONFLICT (cluster_id) DO NOTHING
        """,
            (count,),
        )
    conn.commit()


def main():
    conn = psycopg2.connect(DATABASE_URL)
    clusters = get_clusters(conn)
    print(f"Labeling {len(clusters)} clusters...")

    for cluster_id, ticket_count in clusters:
        messages = sample_messages(conn, cluster_id)
        result = label_cluster(messages)
        verified, unverified = verify_quotes(result["evidence_quotes"], messages)
        result["evidence_quotes"] = verified

        if unverified:
            print(
                f"  WARNING: cluster {cluster_id} had {len(unverified)} unverified quote(s)"
            )

        save_label(conn, cluster_id, ticket_count, len(messages), result, unverified)
        print(
            f'  Cluster {cluster_id} ({ticket_count} tickets): "{result["theme_name"]}"'
        )

    label_noise(conn)
    conn.close()
    print("\nDone. Saved to cluster_labels.")


if __name__ == "__main__":
    main()
