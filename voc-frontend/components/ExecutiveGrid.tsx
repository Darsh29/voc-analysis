import { formatCount } from '@/lib/format'
import type { ClassifiedTheme } from '@/lib/types'

type Props = { themes: ClassifiedTheme[] }

export default function ExecutiveGrid({ themes }: Props) {
  return (
    <section className="px-6 py-6 md:px-10">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {themes.map((theme) => (
          <div
            key={theme.id}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-4"
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-medium text-[var(--text)]">{theme.name}</h3>
              <span className="shrink-0 text-lg leading-none">{theme.emoji}</span>
            </div>
            <p className="mt-2 text-xs text-[var(--text-dim)]">{theme.statusLabel}</p>
            <p className="font-data mt-3 text-sm text-[var(--text)]">
              {formatCount(theme.ticketCount)} tickets
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
