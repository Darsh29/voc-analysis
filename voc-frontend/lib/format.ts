export function formatPercent(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`
}

export function formatSignedPoints(points: number, digits = 1): string {
  const sign = points > 0 ? '+' : ''
  return `${sign}${points.toFixed(digits)}`
}

export function formatSignedPercent(percent: number | null, digits = 0): string {
  if (percent === null) return 'n/a'
  const sign = percent > 0 ? '+' : ''
  return `${sign}${percent.toFixed(digits)}%`
}

export function formatHours(hours: number, digits = 1): string {
  return `${hours.toFixed(digits)}h`
}

export function formatCsat(csat: number | null, digits = 2): string {
  if (csat === null) return 'n/a'
  return csat.toFixed(digits)
}

export function formatCount(count: number): string {
  return count.toLocaleString()
}
