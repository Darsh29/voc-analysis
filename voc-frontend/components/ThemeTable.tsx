'use client'

import { Fragment, useMemo, useState } from 'react'
import Sparkline from './Sparkline'
import { formatCsat, formatHours, formatPercent, formatSignedPercent } from '@/lib/format'
import { FILTER_OPTIONS, matchesFilter, statusColor, type FilterKey } from '@/lib/statusColor'
import type { ClassifiedTheme } from '@/lib/types'

type SortKey =
  | 'name'
  | 'ticketCount'
  | 'growthPercent'
  | 'avgCsat'
  | 'avgResolutionHours'
  | 'repeatContactRate'
  | 'churnRate'

type SortState = { key: SortKey; direction: 'asc' | 'desc' }

type Props = {
  themes: ClassifiedTheme[]
  selectedThemeId: number | null
  onClearSelection: () => void
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'name', label: 'Theme' },
  { key: 'ticketCount', label: 'Tickets' },
  { key: 'growthPercent', label: '9-day trend' },
  { key: 'avgCsat', label: 'CSAT' },
  { key: 'avgResolutionHours', label: 'Resolution' },
  { key: 'repeatContactRate', label: 'Repeat %' },
  { key: 'churnRate', label: 'Churn %' },
]

function sortValue(theme: ClassifiedTheme, key: SortKey): number | string {
  if (key === 'name') return theme.name
  if (key === 'growthPercent') return theme.growthPercent ?? -Infinity
  return theme[key] ?? -Infinity
}

export default function ThemeTable({ themes, selectedThemeId, onClearSelection }: Props) {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterKey, setFilterKey] = useState<FilterKey>('all')
  const [sort, setSort] = useState<SortState>({ key: 'ticketCount', direction: 'desc' })
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  const toggleExpanded = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'desc' }
    )
  }

  const selectedTheme = selectedThemeId !== null ? themes.find((t) => t.id === selectedThemeId) : undefined

  const visibleThemes = useMemo(() => {
    if (selectedTheme) return [selectedTheme]

    const query = searchQuery.trim().toLowerCase()
    const filtered = themes.filter(
      (t) => matchesFilter(t.status, filterKey) && (query === '' || t.name.toLowerCase().includes(query))
    )

    const sorted = [...filtered].sort((a, b) => {
      const av = sortValue(a, sort.key)
      const bv = sortValue(b, sort.key)
      let cmp: number
      if (typeof av === 'string' && typeof bv === 'string') cmp = av.localeCompare(bv)
      else cmp = (av as number) - (bv as number)
      return sort.direction === 'asc' ? cmp : -cmp
    })

    return sorted
  }, [themes, selectedTheme, searchQuery, filterKey, sort])

  return (
    <section className="px-6 py-6 md:px-10">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              type="button"
              onClick={() => setFilterKey(opt.key)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                filterKey === opt.key
                  ? 'border-[var(--text)] text-[var(--text)]'
                  : 'border-[var(--border)] text-[var(--text-dim)] hover:text-[var(--text)]'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search themes…"
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--text-dim)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)] sm:w-64"
        />
      </div>

      {selectedTheme && (
        <div className="mb-3 flex items-center gap-2 text-xs text-[var(--text-dim)]">
          <span>
            Filtered to <span className="text-[var(--text)]">&ldquo;{selectedTheme.name}&rdquo;</span> from
            chart selection.
          </span>
          <button
            type="button"
            onClick={onClearSelection}
            className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[var(--text)] hover:border-[var(--text)]"
          >
            Clear
          </button>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className="cursor-pointer select-none whitespace-nowrap px-3 py-2 text-left text-xs font-medium text-[var(--text-dim)] hover:text-[var(--text)]"
                >
                  {col.label}
                  {sort.key === col.key && (sort.direction === 'asc' ? ' ▲' : ' ▼')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleThemes.map((theme) => {
              const isExpanded = expandedIds.has(theme.id)
              return (
                <Fragment key={theme.id}>
                  <tr
                    onClick={() => toggleExpanded(theme.id)}
                    className="cursor-pointer border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--surface)]"
                  >
                    <td className="px-3 py-2">
                      <span className="mr-1.5">{theme.emoji}</span>
                      {theme.name}
                    </td>
                    <td className="font-data px-3 py-2">{theme.ticketCount.toLocaleString()}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Sparkline dailyVolume={theme.dailyVolume} color={statusColor(theme.status)} />
                        <span className="font-data whitespace-nowrap text-xs">
                          {formatSignedPercent(theme.growthPercent)}
                          {theme.volatile && (
                            <span className="ml-1 rounded bg-[var(--border)] px-1 py-0.5 text-[10px] text-[var(--text-dim)]">
                              volatile
                            </span>
                          )}
                        </span>
                      </div>
                    </td>
                    <td className="font-data px-3 py-2">
                      {formatCsat(theme.avgCsat)}
                      {theme.lowN && (
                        <span className="ml-1 rounded bg-[var(--border)] px-1 py-0.5 text-[10px] text-[var(--text-dim)]">
                          low n
                        </span>
                      )}
                    </td>
                    <td className="font-data px-3 py-2">{formatHours(theme.avgResolutionHours)}</td>
                    <td className="font-data px-3 py-2">{formatPercent(theme.repeatContactRate)}</td>
                    <td className="font-data px-3 py-2">{formatPercent(theme.churnRate)}</td>
                  </tr>
                  {isExpanded && (
                    <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                      <td colSpan={COLUMNS.length} className="px-3 py-3">
                        <div className="text-xs font-medium uppercase tracking-wide text-[var(--text-dim)]">
                          Evidence quotes
                        </div>
                        <ul className="mt-2 space-y-1.5">
                          {theme.evidenceQuotes.map((quote, i) => (
                            <li key={i} className="text-sm italic text-[var(--text)]">
                              &ldquo;{quote}&rdquo;
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
