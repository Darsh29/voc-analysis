type Props = { generatedAt: string }

const PIPELINE_STAGES = [
  'Ingest',
  'Clean',
  'Embed (Voyage AI)',
  'Cluster',
  'Label clusters (Claude)',
  'Consolidate themes',
  'Analyze',
  'Export',
]

export default function Footer({ generatedAt }: Props) {
  const generated = new Date(generatedAt)
  const formatted = Number.isNaN(generated.getTime())
    ? generatedAt
    : generated.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      })

  return (
    <footer className="mt-auto border-t border-[var(--border)] px-6 py-6 md:px-10">
      <p className="text-xs text-[var(--text-dim)]">
        Generated <span className="font-data">{formatted}</span>
      </p>
      <p className="mt-1 text-xs text-[var(--text-dim)]">
        Pipeline: {PIPELINE_STAGES.join(' → ')}
      </p>
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        Point-in-time snapshot. No live data — this report is not refreshed automatically.
      </p>
    </footer>
  )
}
