# CookUnity Voice of Customer Analysis

An AI-native pipeline that turns 10,000 anonymized CookUnity support tickets
into a small set of discovered themes, evidence-backed by real customer
messages, connected to trend and outcome data (CSAT, churn, resolution time,
repeat contact) — built for the CookUnity AI Engineer take-home assessment.

**Live output:** open `report.html` in any browser (no server needed) for the
generated report. See [Quick start](#quick-start) to regenerate it from scratch.

## How this maps to their evaluation criteria

| Their criterion | Where it's addressed |
|---|---|
| **Product judgment** — are the insights useful and understandable? | The report's [Key Findings](#) box states conclusions in plain English before any chart/table; non-actionable clusters (e.g. "thank you" replies) are explicitly excluded rather than ranked as issues — see [Key design decisions](#key-design-decisions). |
| **AI engineering** — grounded, explainable, robust to noisy text? | Every evidence quote is programmatically verified against source text (1 of 64 caught and flagged, not silently trusted); clustering is fully reproducible (`random_state=42`); the real degenerate-clustering failure and its UMAP fix are documented in [Failure modes](#failure-modes--known-limitations). |
| **Data handling** — pagination, missing fields, sensitive text? | `ingest.py` pages until `next_cursor` is null with no hardcoded limit; `NULL` is preserved as "unknown," never coerced; redacted message text is never logged beyond what's needed — see [Assumptions](#assumptions). |
| **Execution** — easy to run, inspect, extend? | Single-command stages, a static `report.html` requiring no server, and a genuine fresh-clone test (separate folder, fresh venv, fresh Postgres volume) that found and fixed two real setup gaps before this was called done — see [Failure modes](#failure-modes--known-limitations). |

## Results at a glance

> Discount and promotion not applied correctly is the largest actionable theme, with 988 tickets, up +39% over the 9-day window. Subscription cancellation requests has the strongest link to bad outcomes: churn is 32.6% (+22.7 percentage points above the 10.0% baseline). Wrong meal delivered inside correct packaging grew fastest over the 9-day window (+98%) — with 137 tickets this run, treat the exact percentage with some caution (see 'volatile' flag below).

## What this does, in one paragraph

The pipeline ingests all available tickets via the provided API, cleans and
normalizes the redacted customer messages, embeds them, clusters them by
semantic similarity, asks Claude to independently name and provide evidence
for each cluster (without ever seeing CookUnity's existing category labels),
consolidates near-duplicate themes and flags non-complaint clusters, connects
the resulting 23 actionable themes (plus 1 explicitly flagged non-complaint
theme) to trend and outcome data, and renders it all as a single static
HTML report.

## Quick start

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

docker compose up -d             # starts Postgres

# copy .env.example to .env and fill in:
#   ANTHROPIC_API_KEY, VOYAGE_API_KEY, VOC_API_KEY, DATABASE_URL
cp .env.example .env

python ingest.py                 # ~10,000 tickets -> raw_tickets
python clean.py                  # -> clean_tickets
python embed.py                  # -> ticket_embeddings (Voyage API)
python cluster.py                # -> ticket_clusters (HDBSCAN + UMAP)
python label_clusters.py         # -> cluster_labels (Claude API)
python consolidate_themes.py     # -> parent_themes (Claude API)
python analyze.py                # -> theme_outcomes, theme_daily_volume
python report.py                 # -> report.html
```

Open `report.html` directly in a browser — no build step, no dev server.

## Architecture

```
/meta -> ingest -> clean -> embed -> cluster -> label -> consolidate -> analyze -> report
```

| Stage | File | Tool | Why this tool |
|---|---|---|---|
| Reconnaissance | — | manual `/meta` + `/tickets` calls | Read the API's own documentation and sampled real records before writing any code — surfaced the real page-size cap, the fact that `customer_messages` is a list, and several undocumented fields, none of which were guessable from the spec alone. |
| Ingestion | `ingest.py` | Python + Postgres (Docker) | Deterministic, cheap. Pages via `next_cursor` with no hardcoded limit, writes raw JSON to `raw_tickets` immediately per page, `ON CONFLICT DO NOTHING` for safe re-runs. |
| Cleaning | `clean.py` | Python (regex, `ftfy`) | Deterministic. Dedupes near-universal duplicate messages, strips quoted-email/marketing content, removes mobile-client signatures, normalizes unrecoverable encoding artifacts — all validated against real samples before inclusion. |
| Embedding | `embed.py` | Voyage AI (`voyage-4`) | Turns cleaned text into vectors so "similar meaning" becomes computable. Anthropic's recommended embeddings partner; `input_type=None` since this is symmetric clustering, not asymmetric query/document retrieval. |
| Clustering | `cluster.py` | UMAP + HDBSCAN | Density-based clustering finds the natural number of themes without guessing `k` up front, and can mark genuinely one-off tickets as noise rather than forcing them into a wrong bucket. UMAP reduces to 10 dimensions first — HDBSCAN directly on 1024-dim embeddings found zero structure (distance concentration; see Failure modes). |
| Labeling | `label_clusters.py` | Claude (`claude-sonnet-5`) | This is the one stage that needs actual judgment, not math — naming what a cluster of real complaints is about, and picking honest evidence. Deliberately does not see CookUnity's existing `contact_reason` labels (see Assumptions). |
| Consolidation | `consolidate_themes.py` | Claude (`claude-sonnet-5`) | A second, different LLM task: reasoning about relationships between 32 already-discovered labels — merging duplicates, flagging non-complaint clusters (e.g. "thank you" replies) — rather than re-reading raw text. |
| Analysis | `analyze.py` | Python + SQL | Once tickets carry a theme, "is this growing" and "does this correlate with bad outcomes" are counting and correlation problems. SQL is exact and auditable; an LLM restating numbers from a prompt would be a needless source of error. |
| Report | `report.py` | Python -> static HTML | Single self-contained file, zero JS dependencies (evidence toggles use native `<details>`), opens in any browser. Chosen specifically to satisfy "easy to run, inspect, extend" with certainty. |

## Interactive frontend

As an additional deliverable, `voc-frontend/` is a Next.js app that makes
the same underlying analysis explorable interactively — an Executive
Summary / Full Detail toggle, a severity-vs-growth scatter chart with
click-to-filter, and a sortable/searchable theme table with per-theme
sparklines and evidence quotes. It was built with Claude Code against a
written spec (`CLAUDE_CODE_SPEC.md`), reads the same analysis via a static
data export (`export_data.py` -> `report-data.json`) rather than a live
database connection, and deploys to Vercel with zero configuration.

## Key design decisions

- **Churn, not CSAT, drives the report's severity axis.** CSAT covers only
  14.9% of tickets (many themes have single-digit sample sizes); churn signal
  covers 91.5% of tickets — a materially more trustworthy basis for the
  headline visual. CSAT is still shown per-theme with its real sample size.
- **"Trend" is 9-day directional volume, not week-over-week growth.** The
  dataset spans exactly 9 days (`2026-04-23` to `2026-05-01`, confirmed via
  `MIN/MAX(ticket_date)`). Claiming multi-week trends from 9 days of data
  would overstate what the data supports — this is stated explicitly rather
  than implied.
- **Theme discovery is independent of CookUnity's existing labels.** Claude
  never sees `main_contact_reason`/`contact_reason` while naming clusters —
  intentional, since `/meta` itself flags these as "may be noisy," and
  independent discovery is a stronger, less circular result than letting an
  existing (possibly imperfect) category bias the naming step.
- **Every evidence quote is verified against source text after generation**,
  not just trusted. Of 64 quotes generated during labeling, 1 failed exact
  match — inspection showed light paraphrasing ("seven" -> "7", one word
  inserted), not fabrication. Caught automatically, stored separately, not
  silently corrected or silently trusted.
- **Non-actionable clusters are flagged, not hidden or ranked as issues.**
  Three clusters (customer gratitude/ticket-closing replies) clustered by
  text similarity but aren't complaints — shown in their own section with an
  explanation, so a support lead never sees "customers say thank you" ranked
  as a top issue.
- **Confidence flags, not false precision.** Both CSAT (`low n` below 20
  samples) and trend percentage (`volatile` below 150 total tickets) carry
  explicit low-confidence tags in the report rather than presenting every
  number with equal certainty regardless of the sample behind it.

## Assumptions

- `contact_reason`/`main_contact_reason` are treated as informative but
  unreliable source-system metadata, not ground truth — per `/meta`'s own
  caveat that they "may be noisy."
- `NULL` in fields like `has_churn` means genuinely unknown, not `false` —
  never silently coerced.
- `customer_messages` list entries are near-universally duplicated (99.99%
  of tickets) — treated as a systematic export characteristic, not an edge
  case, and deduplicated before any text processing.
- The real API page-size cap is 100 (confirmed empirically — requesting more
  is silently reduced), not the 50 shown in the assignment's example call.
- Undocumented fields beyond `/meta`'s field dictionary (`channel`,
  `business_sla_outcome`, etc.) are used opportunistically, not assumed to be
  a stable contract the way documented fields are.

## Failure modes / known limitations

- **Theme labeling and consolidation (Claude API calls) are not deterministic
  across runs, even on identical input data.** Proven, not theoretical: a
  fresh-clone test ran the entire pipeline twice on the same 10,000 tickets.
  Ingestion, cleaning, embeddings, and clustering came back bit-for-bit
  identical both times (clustering uses a fixed `random_state`). Claude's
  theme names and cluster groupings genuinely differed between runs — e.g.
  "Discount and promotional pricing discrepancies" became "Discount and
  promotion not applied correctly"; two previously-separate clusters merged
  differently; one cluster flipped from "not a complaint" to a real issue.
  Neither run was wrong — this is inherent to LLM-based reasoning, not a bug.
  It does mean anything downstream that assumes exact theme wording is
  fragile: `report.py`'s chart-highlighting logic originally hardcoded three
  theme name strings, which a second real run would have silently broken
  (2 of 3 no longer matched anything). Fixed by selecting highlights from
  the data itself (most severe / fastest-growing / largest actionable theme)
  rather than by name — verified against the actual second run's output.
- **Quote/footer-stripping targets CookUnity-specific literal strings**
  (e.g. "Cookin Inc. (DBA Cook Unity Inc.)"). The *pattern* (date + "wrote:"
  ... footer marker) is structural, but the specific footer text is not
  portable to another company's ticket export without rework.
- **Pasted technical noise (error pages, HTML dumps) is not caught.**
  Measured incidence under 0.1% (6-8 of 10,000 tickets) — confirmed rare
  before deciding not to build a bespoke rule, rather than assumed.
- **Unpredictable creative phrasing survives cleaning.** Two tickets contain
  jokes like "Sent from my thumbs" instead of a real device name — a
  measured, accepted residual (0.02%), not a gap in an otherwise-complete
  rule.
- **Trend percentages are volatile for low-volume themes** — flagged in the
  report (`volatile` tag below 150 total tickets) but the underlying
  first-half/second-half calculation itself doesn't correct for this, it
  only surfaces the caveat.
- **11 tickets have no usable message text** (entirely forwarded marketing
  content) and are excluded from theme discovery, though they still
  contribute to the overall baseline.
- **`ingest.py` originally relied on a manual, undocumented one-time
  `CREATE TABLE` step** run directly in `psql` before the script existed —
  meaning a fresh clone would fail on the very first run with
  `relation "raw_tickets" does not exist`. Found via fresh-clone testing,
  fixed by having `ingest.py` create its own table, consistent with every
  other stage in the pipeline.
- **This has now been run start-to-finish on a genuinely fresh clone**
  (separate folder, fresh venv, fresh Postgres volume, no manual setup
  beyond following this README) — confirmed working after the two fixes
  above. Both gaps above were found by that process, not assumed away.

## Next steps

- Consider pinning `temperature=0` on the Claude labeling/consolidation
  calls as a partial mitigation for run-to-run naming variance — worth
  testing whether it meaningfully increases consistency, since even
  temperature 0 doesn't guarantee identical output from an LLM the way a
  fixed `random_state` does for clustering.
- dbt models over the current raw SQL in `analyze.py`, for testable,
  documented transformations if this became a recurring (not one-off) report.
- An MCP server exposing `get_theme_trends`/`get_ticket_evidence` so a
  support lead could query this data conversationally instead of reading a
  static file.
- A small Next.js/Vercel frontend for live filtering and sorting, once the
  static report's core is trusted.
- Compare discovered themes against `contact_reason` explicitly (which
  categories split into multiple discovered themes, which merged) as a
  concrete data point on how the existing categorization compares to
  independent discovery.

## Repo structure

```
ingest.py                 Step 2 — API pagination -> raw_tickets
clean.py                  Step 3 — text cleaning -> clean_tickets
embed.py                  Step 4 — Voyage embeddings -> ticket_embeddings
cluster.py                Step 5 — UMAP + HDBSCAN -> ticket_clusters
label_clusters.py         Step 6 — Claude labeling -> cluster_labels
consolidate_themes.py     Step 6 — Claude consolidation -> parent_themes
analyze.py                Step 7 — trend/outcome SQL -> theme_outcomes, theme_daily_volume
report.py                 Step 8 — generates report.html
export_data.py            Step 8b — exports theme/baseline data -> report-data.json (for voc-frontend/)
experiment_mojibake.py    Diagnostic: validated the encoding-fix approach (not part of the pipeline)
experiment_quote_strip.py Diagnostic: validated the quote-stripping approach (not part of the pipeline)
docker-compose.yml        Postgres container definition
requirements.txt          Pinned dependencies
.env.example              Required environment variables (no real secrets)
CLAUDE_CODE_SPEC.md       Build spec for voc-frontend/, written for Claude Code to build against
voc-frontend/             Interactive Next.js report — reads report-data.json, deployed on Vercel
```
