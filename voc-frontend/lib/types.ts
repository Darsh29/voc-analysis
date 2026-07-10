// Shape of report-data.json (see CLAUDE_CODE_SPEC.md). Read-only snapshot.

export type DailyVolume = { date: string; count: number }

export type Theme = {
  id: number
  name: string
  isActionable: boolean
  ticketCount: number
  avgCsat: number | null
  csatSampleSize: number
  avgResolutionHours: number
  repeatContactRate: number
  churnRate: number
  churnSampleSize: number
  evidenceQuotes: string[]
  dailyVolume: DailyVolume[]
}

export type ReportData = {
  generatedAt: string
  dateRange: { start: string; end: string }
  baseline: {
    avgCsat: number
    avgResolutionHours: number
    repeatContactRate: number // 0-1
    churnRate: number // 0-1
  }
  themes: Theme[]
  noiseCount: number
  emptyMessageCount: number
}

// Status vocabulary from the spec's classification ladder.
export type Status = 'critical' | 'severe' | 'growing' | 'healthy' | 'steady'

// A theme enriched with the derived, plain-language classification.
export type ClassifiedTheme = Theme & {
  severityPercentagePoints: number
  growthPercent: number | null
  status: Status
  emoji: string
  statusLabel: string
  volatile: boolean // ticketCount < 150
  lowN: boolean // csatSampleSize < 20
}
