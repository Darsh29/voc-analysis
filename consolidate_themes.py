"""
FILE: consolidate_themes.py
PURPOSE: Takes the 32 raw cluster labels from label_clusters.py and groups
them into a smaller set of parent themes, while flagging which groups are
genuine customer complaints vs. non-issue clusters (e.g. "thank you"
replies) that clustered together by text similarity but aren't actionable
support themes.
WHY THIS APPROACH: Reading the 32 raw labels side by side showed real
duplication (six separate cancellation-flavored clusters, two near-
identical delivery-delay clusters) and four clusters that are customer
gratitude/confirmation messages, not complaints. Text-similarity
clustering correctly grouped these by how similar the WORDING is, but
that isn't the same as grouping by actual business meaning — closing
that gap requires judgment, which is why this is a second LLM call
rather than a manual keyword-merge script.
INPUT: cluster_labels table (Postgres) — all 32 real cluster labels
(noise/-1 excluded — it's already its own explicit bucket, not a
candidate for merging into anything).
OUTPUT: parent_themes table (Postgres) — one row per consolidated theme,
with the list of raw cluster_ids it covers, an is_actionable_issue flag,
and the reasoning for that flag.
"""

import os
import json
import time
import psycopg2
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL = "claude-sonnet-5"

client = Anthropic()


def extract_text(response):
    """Claude's response.content can include a ThinkingBlock before the
    actual text block — don't assume content[0] is always the answer.
    Find the first block that actually has text."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    raise ValueError("No text block found in response")


def get_cluster_labels(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cluster_id, theme_name, description, ticket_count
            FROM cluster_labels
            WHERE cluster_id != -1
            ORDER BY cluster_id
        """)
        return cur.fetchall()


def build_prompt(clusters):
    listing = "\n".join(
        f'[{cid}] "{name}" ({count} tickets) — {desc}'
        for cid, name, desc, count in clusters
    )
    return f"""Below are {len(clusters)} customer support themes, each discovered independently from clustering real ticket text. Some of these describe the SAME underlying issue using different wording. Some are NOT actual complaints at all (e.g. customers saying thank you, confirming receipt) — they clustered together by text similarity but aren't support issues.

{listing}

Group these into parent themes. Respond with ONLY a JSON object (no markdown fences, no preamble):
{{
  "parent_themes": [
    {{
      "parent_name": "a clear, specific name for the consolidated theme",
      "cluster_ids": [list of the cluster ID numbers from above that belong to this parent theme],
      "is_actionable_issue": true or false — false if this is gratitude/confirmation/non-complaint content, not a real support issue,
      "rationale": "one sentence explaining why these clusters were grouped together, or why this was flagged as non-actionable"
    }}
  ]
}}

Every cluster ID from the list above must appear in exactly one parent theme. Do not omit any."""


def consolidate(clusters, retries=3):
    prompt = build_prompt(clusters)
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text(response).strip()
            text = (
                text.removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return json.loads(text)
        except Exception as e:
            wait = 2**attempt
            print(f"  Call failed ({e}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Failed to consolidate after all retries")


def validate_coverage(result, clusters):
    """Confirms every original cluster_id appears in exactly one parent
    theme — catches the model dropping or duplicating a cluster."""
    expected = {c[0] for c in clusters}
    seen = []
    for pt in result["parent_themes"]:
        seen.extend(pt["cluster_ids"])

    missing = expected - set(seen)
    duplicated = [cid for cid in seen if seen.count(cid) > 1]

    if missing:
        print(f"  WARNING: cluster_ids missing from any parent theme: {missing}")
    if duplicated:
        print(
            f"  WARNING: cluster_ids assigned to multiple parent themes: {set(duplicated)}"
        )
    return not missing and not duplicated


def save_parent_themes(conn, result):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parent_themes (
                id SERIAL PRIMARY KEY,
                parent_name TEXT,
                cluster_ids JSONB,
                is_actionable_issue BOOLEAN,
                rationale TEXT,
                total_tickets INTEGER
            )
        """)
        cur.execute(
            "DELETE FROM parent_themes"
        )  # safe to fully replace — small table, cheap to regenerate

        # need ticket counts per cluster to compute each parent theme's total
        cur.execute(
            "SELECT cluster_id, ticket_count FROM cluster_labels WHERE cluster_id != -1"
        )
        counts = dict(cur.fetchall())

        for pt in result["parent_themes"]:
            total = sum(counts.get(cid, 0) for cid in pt["cluster_ids"])
            cur.execute(
                """
                INSERT INTO parent_themes (parent_name, cluster_ids, is_actionable_issue, rationale, total_tickets)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    pt["parent_name"],
                    json.dumps(pt["cluster_ids"]),
                    pt["is_actionable_issue"],
                    pt["rationale"],
                    total,
                ),
            )
    conn.commit()


def main():
    conn = psycopg2.connect(DATABASE_URL)
    clusters = get_cluster_labels(conn)
    print(f"Consolidating {len(clusters)} cluster labels into parent themes...")

    result = consolidate(clusters)
    ok = validate_coverage(result, clusters)

    save_parent_themes(conn, result)
    conn.close()

    print(f"\n{'PASSED' if ok else 'FAILED'} coverage check.\n")
    for pt in result["parent_themes"]:
        tag = "ISSUE" if pt["is_actionable_issue"] else "not a complaint"
        print(f"[{tag}] {pt['parent_name']} — clusters {pt['cluster_ids']}")
        print(f"    {pt['rationale']}")

    print("\nDone. Saved to parent_themes.")


if __name__ == "__main__":
    main()
