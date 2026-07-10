import type { ClassifiedTheme } from './types'

// Key Findings must be computed at render time from whatever theme names
// currently occupy these roles — theme labeling is non-deterministic across
// pipeline runs, so nothing here may hardcode a theme name.

export function buildKeyFindings(themes: ClassifiedTheme[]): string {
  if (themes.length === 0) return 'No actionable themes were found in this dataset.'

  const mostSevere = themes.reduce((a, b) =>
    b.severityPercentagePoints > a.severityPercentagePoints ? b : a
  )
  const largest = themes.reduce((a, b) => (b.ticketCount > a.ticketCount ? b : a))

  // Mirrors report.py's candidate filtering: a theme with no reliable trend
  // (growthPercent === null) is never eligible to be "fastest growing."
  const growable = themes.filter(
    (t): t is ClassifiedTheme & { growthPercent: number } => t.growthPercent !== null
  )
  const fastestGrowing =
    growable.length > 0 ? growable.reduce((a, b) => (b.growthPercent > a.growthPercent ? b : a)) : null

  const sentences: string[] = []

  sentences.push(
    `"${mostSevere.name}" is the most severe theme, running ${mostSevere.severityPercentagePoints.toFixed(
      1
    )} percentage points above baseline churn.`
  )

  if (fastestGrowing === null) {
    sentences.push('No theme has enough daily-volume data to identify a fastest-growing trend.')
  } else if (fastestGrowing.id === mostSevere.id) {
    sentences.push(
      `It is also the fastest-growing theme, up ${fastestGrowing.growthPercent.toFixed(
        0
      )}% in daily volume from the start to the end of the window.`
    )
  } else {
    sentences.push(
      `"${fastestGrowing.name}" is climbing fastest, up ${fastestGrowing.growthPercent.toFixed(
        0
      )}% in daily volume from the start to the end of the window.`
    )
  }

  if (largest.id === mostSevere.id || (fastestGrowing !== null && largest.id === fastestGrowing.id)) {
    sentences.push(
      `"${largest.name}" is also the largest theme by volume, with ${largest.ticketCount.toLocaleString()} tickets.`
    )
  } else {
    sentences.push(
      `"${largest.name}" is the largest theme by volume, with ${largest.ticketCount.toLocaleString()} tickets.`
    )
  }

  return sentences.join(' ')
}
