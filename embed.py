"""
FILE: embed.py
PURPOSE: Generates Voyage AI embeddings for each ticket's clean_message
and stores them for clustering in Step 5.
WHY THIS APPROACH: Uses input_type=None rather than "document" — Voyage's
input_type is designed for asymmetric query-vs-document retrieval, but
this task is symmetric (comparing tickets to each other, not to a query),
so the retrieval-oriented prompt Voyage would otherwise prepend doesn't
fit and isn't used. Batches requests (128 per call, per Voyage's own
documented pattern) rather than one API call per ticket, for cost and
throughput. Embeddings are stored in their own table, separate from
clean_tickets, so the embedding model can be changed/rerun later without
touching the cleaning pipeline upstream.
INPUT: clean_tickets table (Postgres) — reads clean_message per ticket.
OUTPUT: ticket_embeddings table (Postgres) — one float8[] vector per ticket.
"""

import os
import time
import psycopg2
import voyageai
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
VOYAGE_MODEL = "voyage-4"
BATCH_SIZE = 128

vo = voyageai.Client()  # reads VOYAGE_API_KEY from env automatically


def create_embeddings_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ticket_embeddings (
                ticket_id TEXT PRIMARY KEY,
                embedding FLOAT8[] NOT NULL,
                model TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT now()
            )
        """)
    conn.commit()


def fetch_batches(conn, batch_size=BATCH_SIZE):
    """Yields (ticket_ids, texts) batches, skipping tickets with no message."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ticket_id, clean_message FROM clean_tickets
            WHERE clean_message IS NOT NULL AND clean_message != ''
            ORDER BY ticket_id
        """)
        rows = cur.fetchall()

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        ticket_ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]
        yield ticket_ids, texts


def embed_with_retry(texts, retries=3):
    for attempt in range(retries):
        try:
            result = vo.embed(texts, model=VOYAGE_MODEL, input_type=None)
            return result.embeddings
        except Exception as e:
            wait = 2**attempt
            print(f"  Embedding call failed ({e}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Failed to embed batch after all retries")


def save_batch(conn, ticket_ids, embeddings):
    with conn.cursor() as cur:
        for ticket_id, embedding in zip(ticket_ids, embeddings):
            cur.execute(
                """
                INSERT INTO ticket_embeddings (ticket_id, embedding, model)
                VALUES (%s, %s, %s)
                ON CONFLICT (ticket_id) DO NOTHING
                """,
                (ticket_id, embedding, VOYAGE_MODEL),
            )
    conn.commit()


def main():
    conn = psycopg2.connect(DATABASE_URL)
    create_embeddings_table(conn)

    total = 0
    for ticket_ids, texts in fetch_batches(conn):
        embeddings = embed_with_retry(texts)
        save_batch(conn, ticket_ids, embeddings)
        total += len(ticket_ids)
        print(f"Embedded {total} tickets so far...")

    conn.close()
    print(f"Done. Embedded {total} tickets total.")


if __name__ == "__main__":
    main()
