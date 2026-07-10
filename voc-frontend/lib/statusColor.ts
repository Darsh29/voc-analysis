import type { Status } from './types'

// Chart/table dot colors collapse the 5-status ladder onto the 3-color
// design system: amber (worse than baseline), teal (better), gray (neutral).
export function statusColor(status: Status): string {
  switch (status) {
    case 'critical':
    case 'severe':
      return 'var(--amber)'
    case 'healthy':
      return 'var(--teal)'
    case 'growing':
    case 'steady':
      return 'var(--text-dim)'
  }
}

export const FILTER_OPTIONS = [
  { key: 'all', label: 'All' },
  { key: 'urgent', label: '🔴 Urgent' },
  { key: 'growing', label: '🟠 Climbing' },
  { key: 'healthy', label: '🟢 Better than usual' },
] as const

export type FilterKey = (typeof FILTER_OPTIONS)[number]['key']

export function matchesFilter(status: Status, filter: FilterKey): boolean {
  if (filter === 'all') return true
  if (filter === 'urgent') return status === 'critical' || status === 'severe'
  if (filter === 'growing') return status === 'growing'
  if (filter === 'healthy') return status === 'healthy'
  return true
}
