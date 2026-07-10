# Build Spec: Voice of Customer Interactive Report (Next.js)

## Context

This is the interactive frontend for a completed data pipeline (Python +
Postgres + Claude + Voyage AI) that discovered 24 customer support themes
from 10,000 anonymized tickets. All analysis is DONE — this app only needs
to render `report-data.json` (already exported, sitting in this folder).
**No database connection, no API calls, no live data fetching of any kind.**
This is a point-in-time snapshot report, not a live dashboard.

## Setup

```bash
npx create-next-app@latest voc-frontend --typescript --tailwind --eslint --app --no-src-dir
cd voc-frontend
```

Copy `report-data.json` into the project root (or `/data`). Import it
directly in the page component — Next.js supports importing `.json` files
as modules natively, no fetch/API route needed:
```ts
import reportData from '../report-data.json'
```

## Data shape (report-data.json)

```ts
type ReportData = {
  generatedAt: string
  dateRange: { start: string; end: string }
  baseline: {
    avgCsat: number
    avgResolutionHours: number
    repeatContactRate: number  // 0-1, multiply by 100 for %
    churnRate: number          // 0-1, multiply by 100 for %
  }
  themes: Array<{
    id: number
    name: string
    isActionable: boolean
    ticketCount: number
    avgCsat: number | null
    csatSampleSize: number
    avgResolutionHours: number
    repeatContactRate: number
    churnRate: number
    churnSampleSize: number
    evidenceQuotes: string[]
    dailyVolume: Array<{ date: string; count: number }>  // 9 entries, YYYY-MM-DD
  }>
  noiseCount: number
  emptyMessageCount: number
}
```

## Design system (match exactly — this is an established dark theme, not a fresh choice)

```css
--bg: #14161c;        /* page background */
--surface: #1c1f28;   /* card backgrounds */
--border: #2c2f3a;
--text: #d8dae0;
--text-dim: #8b8f9e;
--amber: #f2a63c;      /* worse-than-baseline / urgent */
--teal: #3fbf9f;       /* better-than-baseline / healthy */
```
Font: system sans-serif for body/UI text, monospace (e.g. `ui-monospace, "SF Mono", Consolas`) for all numeric data (ticket counts, percentages, dollar-like figures) — this monospace-for-numbers convention is deliberate and should carry through.

## Plain-language classification (port this logic exactly — do not invent new thresholds)

For each actionable theme, compute:
```
severityPercentagePoints = (theme.churnRate - baseline.churnRate) * 100
growthPercent = computed from dailyVolume: (avg of last 4 days - avg of first 4 days) / avg of first 4 days * 100
```

Then classify:
- `severityPercentagePoints > 8 AND growthPercent > 30` → status `critical`, 🔴, "Urgent — worse than usual AND climbing"
- `severityPercentagePoints > 8` → status `severe`, 🔴, "Worse than usual"
- `growthPercent > 30` → status `growing`, 🟠, "Climbing, but outcomes near typical"
- `severityPercentagePoints < -2 AND growthPercent < 10` → status `healthy`, 🟢, "Better than usual, steady"
- otherwise → status `steady`, ⚫, "Roughly typical"

Confidence flags (both must be shown, not hidden):
- `ticketCount < 150` → tag "volatile" next to the trend %
- `csatSampleSize < 20` → tag "low n" next to the CSAT figure

## Required pages/sections (single page, in this order)

1. **Header**: title "Voice of Customer — Theme Report", subtitle with total ticket count, actionable theme count, date range.
2. **Baseline strip**: 4 stat cards (CSAT, resolution hours, repeat contact %, churn %).
3. **Key Findings box**: 2-3 sentences, computed dynamically (NOT hardcoded theme names — see "Dynamic findings" below), styled as a card with a teal left border.
4. **View toggle**: "Executive Summary" vs "Full Detail" — this is the most important UX feature. Executive mode shows only: Key Findings, a simplified card grid of themes (name, emoji status, one-line plain-English blurb, ticket count — no raw numbers table). Full Detail mode shows everything including the chart and the full data table. Toggle should feel instant (client-side state, no reload).
5. **Interactive chart** (Full Detail only): severity (y) vs. growth (x) scatter, one point per actionable theme, sized by ticket count, colored by status (amber/gray/teal). Use `recharts` `ScatterChart`. **Clicking a point filters the table below to that single theme** (this is the key interactivity — connects the two views). Axis labels in plain language: x-axis "More tickets over time →", y-axis "↑ Worse customer outcomes". Include a "how to read this" one-line sentence above the chart.
6. **Theme table/cards** (Full Detail): search box (filters by name), filter buttons (All / 🔴 Urgent / 🟠 Climbing / 🟢 Better than usual), sortable column headers, and **a small sparkline (mini line chart of `dailyVolume`) per row** instead of just the growth %age — use `recharts` `LineChart` with hidden axes, ~80px wide, inline in the row. Expandable evidence quotes per theme (click to show/hide, use the real `evidenceQuotes` array — never invent quotes).
7. **Excluded section**: list non-actionable themes (`isActionable: false`) plus `noiseCount` and `emptyMessageCount`, each with a one-line explanation of why excluded.
8. **Footer**: generation timestamp, pipeline stage list.

## Dynamic findings (critical — do not hardcode theme names)

Theme labeling is proven non-deterministic across pipeline runs (verified via testing — same input data produced different theme names/groupings on two separate runs). The Key Findings sentences and any "spotlight" logic MUST be computed from `report-data.json` at render time:
- Find the actionable theme with highest `severityPercentagePoints` → "most severe"
- Find the actionable theme with highest `growthPercent` → "fastest growing"
- Find the actionable theme with highest `ticketCount` → "largest"

Write 2-3 sentences using whichever theme names and real numbers currently occupy those three roles — never assume a specific theme name will exist.

## Deployment

Vercel, zero-config: `next build` works with no environment variables and no external services, since all data is the committed JSON file. Connect the GitHub repo to Vercel and deploy — no environment variables need to be set.

## Explicitly out of scope

- No authentication, no live database, no API routes, no server actions that fetch external data.
- No editing/writing capability — this is read-only, presentation of already-finished analysis.
- Do not invent additional themes, quotes, or numbers not present in `report-data.json`.
