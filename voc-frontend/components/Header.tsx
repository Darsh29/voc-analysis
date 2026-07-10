import { formatCount } from '@/lib/format'

type Props = {
  totalTickets: number
  actionableThemeCount: number
  dateRange: { start: string; end: string }
}

export default function Header({ totalTickets, actionableThemeCount, dateRange }: Props) {
  return (
    <header className="border-b border-[var(--border)] px-6 py-8 md:px-10">
      <p className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--teal)]">
        VOC Analytics
      </p>
      <h1 className="text-2xl font-semibold text-[var(--text)] md:text-3xl">
        Voice of Customer — Theme Report
      </h1>
      <p className="mt-2 text-sm text-[var(--text-dim)] md:text-base">
        <span className="font-data">{formatCount(totalTickets)}</span> tickets analyzed ·{' '}
        <span className="font-data">{actionableThemeCount}</span> actionable themes ·{' '}
        <span className="font-data">
          {dateRange.start} – {dateRange.end}
        </span>
      </p>
    </header>
  )
}
