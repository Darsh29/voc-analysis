import os
import time
import requests
import psycopg2
import psycopg2.extras
import json
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://voc-analysis-tool.vercel.app/api/takehome/v1"
VOC_API_KEY = os.getenv("VOC_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

HEADERS = {"Authorization": f"Bearer {VOC_API_KEY}"}
PAGE_SIZE = (
    100  # confirmed real max in Step 1 exploration; server caps anything higher anyway
)


def fetch_page(cursor=None, retries=3):
    """Fetch one page of tickets. Retries on transient network failures."""
    params = {"limit": PAGE_SIZE}
    if cursor:
        params["cursor"] = cursor

    for attempt in range(retries):
        try:
            resp = requests.get(
                f"{API_BASE}/tickets", headers=HEADERS, params=params, timeout=30
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            wait = 2**attempt  # exponential backoff: 1s, 2s, 4s
            print(
                f"Request failed ({e}), retrying in {wait}s... (attempt {attempt + 1}/{retries})"
            )
            time.sleep(wait)

    raise RuntimeError("Failed to fetch page after all retries")


def save_page(conn, tickets):
    """Insert a page of raw tickets. Safe to re-run — skips tickets already stored."""
    with conn.cursor() as cur:
        for ticket in tickets:
            cur.execute(
                """
                INSERT INTO raw_tickets (ticket_id, raw_json)
                VALUES (%s, %s)
                ON CONFLICT (ticket_id) DO NOTHING
                """,
                (ticket["ticket_id"], json.dumps(ticket)),
            )
    conn.commit()


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = None
    page_num = 0
    total_ingested = 0

    while True:
        page_num += 1
        print(f"Fetching page {page_num}...")
        data = fetch_page(cursor)

        tickets = data.get("data", [])
        save_page(conn, tickets)
        total_ingested += len(tickets)
        print(f"  -> stored {len(tickets)} tickets (running total: {total_ingested})")

        cursor = data.get("next_cursor")
        if not cursor:
            print("No next_cursor returned — ingestion complete.")
            break

    conn.close()
    print(f"Done. Total tickets ingested: {total_ingested}")


if __name__ == "__main__":
    main()
