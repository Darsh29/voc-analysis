import { formatCsat, formatHours, formatPercent } from '@/lib/format'
import type { ReportData } from '@/lib/types'

type Props = { baseline: ReportData['baseline'] }

export default function BaselineStrip({ baseline }: Props) {
  const stats = [
    { label: 'Avg CSAT', value: formatCsat(baseline.avgCsat) },
    { label: 'Avg Resolution Time', value: formatHours(baseline.avgResolutionHours) },
    { label: 'Repeat Contact Rate', value: formatPercent(baseline.repeatContactRate) },
    { label: 'Churn Rate', value: formatPercent(baseline.churnRate) },
  ]

  return (
    <section className="px-6 py-6 md:px-10">
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-[var(--text-dim)]">
        Baseline (all tickets)
      </h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-4"
          >
            <div className="text-xs text-[var(--text-dim)]">{stat.label}</div>
            <div className="font-data mt-1 text-xl font-semibold text-[var(--text)] md:text-2xl">
              {stat.value}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
