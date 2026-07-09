"""
FILE: cluster.py
PURPOSE: Reduces ticket embeddings to a lower-dimensional space via UMAP,
then runs HDBSCAN on the reduced space to discover natural theme groupings.
WHY THIS APPROACH: First attempt ran HDBSCAN directly on the raw 1024-dim
Voyage embeddings and found ZERO clusters (100% noise). Diagnosed via
pairwise distance statistics: std/mean ratio of 0.12 confirmed distance
concentration, a known effect in high-dimensional spaces where nearly all
points end up roughly equidistant, leaving no density signal for HDBSCAN
to exploit. Fix: UMAP reduces to a much lower dimension (10) while
preserving LOCAL neighborhood structure (unlike PCA, which optimizes for
global variance and doesn't preserve the local relationships a
density-based clustering algorithm depends on). This UMAP -> HDBSCAN
combination is the same established pattern used by tools like BERTopic
for text-embedding clustering, not a novel workaround.
UMAP runs with metric="cosine" (appropriate for normalized embeddings,
and UMAP supports cosine natively, unlike HDBSCAN). HDBSCAN then runs
with metric="euclidean" on the UMAP output — this is standard practice,
since UMAP's reduced space is Euclidean-friendly regardless of the
metric used to build it.
INPUT: ticket_embeddings table (Postgres) — one 1024-dim vector per ticket.
OUTPUT: ticket_clusters table (Postgres) — one cluster_id per ticket
(-1 = noise, no clear theme).
"""

import os
import numpy as np
import psycopg2
import hdbscan
import umap
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
MIN_CLUSTER_SIZE = 50
UMAP_N_COMPONENTS = 10


def load_embeddings(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ticket_id, embedding FROM ticket_embeddings ORDER BY ticket_id"
        )
        rows = cur.fetchall()
    ticket_ids = [r[0] for r in rows]
    vectors = np.array([r[1] for r in rows])
    return ticket_ids, vectors


def reduce_dimensions(vectors):
    reducer = umap.UMAP(
        n_neighbors=15,
        n_components=UMAP_N_COMPONENTS,
        metric="cosine",
        min_dist=0.0,  # standard setting when the output feeds into clustering,
        # not visualization — allows points to pack tightly
        # within a real cluster rather than spreading out for plotting
        random_state=42,  # fixed seed: makes this reproducible run-to-run,
        # important since UMAP is stochastic by default
    )
    reduced = reducer.fit_transform(vectors)
    return reduced


def run_clustering(vectors):
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(vectors)
    return labels, clusterer


def save_clusters(conn, ticket_ids, labels):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ticket_clusters (
                ticket_id TEXT PRIMARY KEY,
                cluster_id INTEGER NOT NULL
            )
        """)
        for ticket_id, label in zip(ticket_ids, labels):
            cur.execute(
                """
                INSERT INTO ticket_clusters (ticket_id, cluster_id)
                VALUES (%s, %s)
                ON CONFLICT (ticket_id) DO UPDATE SET cluster_id = EXCLUDED.cluster_id
                """,
                (ticket_id, int(label)),
            )
    conn.commit()


def main():
    conn = psycopg2.connect(DATABASE_URL)
    ticket_ids, vectors = load_embeddings(conn)
    print(f"Loaded {len(ticket_ids)} embeddings, dimension {vectors.shape[1]}")

    print(f"Reducing to {UMAP_N_COMPONENTS} dimensions via UMAP...")
    reduced = reduce_dimensions(vectors)
    print("UMAP reduction complete.")

    labels, clusterer = run_clustering(reduced)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(labels == -1))
    print(
        f"\nFound {n_clusters} clusters. {n_noise} tickets ({n_noise / len(labels) * 100:.1f}%) labeled as noise."
    )

    unique, counts = np.unique(labels, return_counts=True)
    print("\nCluster sizes:")
    for cluster_id, count in sorted(zip(unique, counts), key=lambda x: -x[1]):
        label_name = "NOISE" if cluster_id == -1 else f"cluster {cluster_id}"
        print(f"  {label_name}: {count} tickets")

    save_clusters(conn, ticket_ids, labels)
    conn.close()
    print("\nDone. Saved to ticket_clusters.")


if __name__ == "__main__":
    main()
