import { formatCount } from '@/lib/format'
import type { Theme } from '@/lib/types'

type Props = {
  nonActionableThemes: Theme[]
  noiseCount: number
  emptyMessageCount: number
}

export default function ExcludedSection({
  nonActionableThemes,
  noiseCount,
  emptyMessageCount,
}: Props) {
  return (
    <section className="px-6 py-6 md:px-10">
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-[var(--text-dim)]">
        Excluded from analysis
      </h2>
      <ul className="space-y-2">
        {nonActionableThemes.map((theme) => (
          <li
            key={theme.id}
            className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
          >
            <span className="text-sm text-[var(--text)]">
              {theme.name}{' '}
              <span className="font-data text-xs text-[var(--text-dim)]">
                ({formatCount(theme.ticketCount)} tickets)
              </span>
            </span>
            <span className="text-xs text-[var(--text-dim)]">
              Excluded: these clustered by text similarity but are not customer complaints
              (confirmations, gratitude, ticket-closing replies).
            </span>
          </li>
        ))}
        <li className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <span className="text-sm text-[var(--text)]">
            Uncategorized (noise){' '}
            <span className="font-data text-xs text-[var(--text-dim)]">
              ({formatCount(noiseCount)} tickets)
            </span>
          </span>
          <span className="text-xs text-[var(--text-dim)]">
            Did not cluster into any coherent theme (one-off or highly individual issues).
          </span>
        </li>
        <li className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <span className="text-sm text-[var(--text)]">
            No usable message text{' '}
            <span className="font-data text-xs text-[var(--text-dim)]">
              ({formatCount(emptyMessageCount)} tickets)
            </span>
          </span>
          <span className="text-xs text-[var(--text-dim)]">
            Message consisted entirely of forwarded marketing content with no customer-authored
            text.
          </span>
        </li>
      </ul>
    </section>
  )
}
