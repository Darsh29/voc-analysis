import type { ClassifiedTheme, ReportData, Status, Theme } from './types'

// Ports the "Plain-language classification" logic from CLAUDE_CODE_SPEC.md
// exactly. Do not invent new thresholds here.

// Mirrors report.py's compute_trend: needs at least 6 days of data, and
// returns null (not 0/Infinity) when the first-4-days average is 0 — "not
// enough data to say anything meaningful," per the Python original.
export function computeGrowthPercent(dailyVolume: Theme['dailyVolume']): number | null {
  const n = dailyVolume.length
  if (n < 6) return null
  const firstFour = dailyVolume.slice(0, 4)
  const lastFour = dailyVolume.slice(Math.max(0, n - 4))
  const avg = (arr: { count: number }[]) =>
    arr.reduce((sum, d) => sum + d.count, 0) / arr.length
  const firstAvg = avg(firstFour)
  const lastAvg = avg(lastFour)
  if (firstAvg === 0) return null
  return ((lastAvg - firstAvg) / firstAvg) * 100
}

function classifyStatus(
  severityPercentagePoints: number,
  growthPercent: number | null
): { status: Status; emoji: string; statusLabel: string } {
  // report.py's display logic treats an unknown trend as 0 via `(growth or 0)`
  // rather than excluding the theme from classification — mirrored here.
  const growth = growthPercent ?? 0
  if (severityPercentagePoints > 8 && growth > 30) {
    return { status: 'critical', emoji: '🔴', statusLabel: 'Urgent — worse than usual AND climbing' }
  }
  if (severityPercentagePoints > 8) {
    return { status: 'severe', emoji: '🔴', statusLabel: 'Worse than usual' }
  }
  if (growth > 30) {
    return { status: 'growing', emoji: '🟠', statusLabel: 'Climbing, but outcomes near typical' }
  }
  if (severityPercentagePoints < -2 && growth < 10) {
    return { status: 'healthy', emoji: '🟢', statusLabel: 'Better than usual, steady' }
  }
  return { status: 'steady', emoji: '⚫', statusLabel: 'Roughly typical' }
}

export function classifyTheme(theme: Theme, baseline: ReportData['baseline']): ClassifiedTheme {
  const severityPercentagePoints = (theme.churnRate - baseline.churnRate) * 100
  const growthPercent = computeGrowthPercent(theme.dailyVolume)
  const { status, emoji, statusLabel } = classifyStatus(severityPercentagePoints, growthPercent)

  return {
    ...theme,
    severityPercentagePoints,
    growthPercent,
    status,
    emoji,
    statusLabel,
    volatile: theme.ticketCount < 150,
    lowN: theme.csatSampleSize < 20,
  }
}

export function classifyThemes(report: ReportData): ClassifiedTheme[] {
  return report.themes
    .filter((t) => t.isActionable)
    .map((t) => classifyTheme(t, report.baseline))
}
