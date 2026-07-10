'use client'

import { useMemo, useState } from 'react'
import Header from './Header'
import BaselineStrip from './BaselineStrip'
import KeyFindingsBox from './KeyFindingsBox'
import ViewToggle, { type ViewMode } from './ViewToggle'
import ExecutiveGrid from './ExecutiveGrid'
import ThemeChart from './ThemeChart'
import ThemeTable from './ThemeTable'
import ExcludedSection from './ExcludedSection'
import Footer from './Footer'
import { classifyThemes } from '@/lib/classify'
import { buildKeyFindings } from '@/lib/findings'
import type { ReportData } from '@/lib/types'

type Props = { report: ReportData }

export default function ReportView({ report }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('executive')
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null)

  const classifiedThemes = useMemo(() => classifyThemes(report), [report])
  const nonActionableThemes = useMemo(
    () => report.themes.filter((t) => !t.isActionable),
    [report]
  )
  // Matches report.py's total_tickets: sum(theme.ticketCount) + noiseCount.
  // emptyMessageCount tickets were never embedded/clustered, so they're
  // shown in the Excluded section but not folded into this total.
  const totalTickets = useMemo(
    () => report.themes.reduce((sum, t) => sum + t.ticketCount, 0) + report.noiseCount,
    [report]
  )
  const keyFindingsText = useMemo(() => buildKeyFindings(classifiedThemes), [classifiedThemes])

  return (
    <div className="mx-auto w-full max-w-6xl">
      <Header
        totalTickets={totalTickets}
        actionableThemeCount={classifiedThemes.length}
        dateRange={report.dateRange}
      />
      <BaselineStrip baseline={report.baseline} />
      <KeyFindingsBox text={keyFindingsText} />

      <div className="px-6 py-4 md:px-10">
        <ViewToggle mode={viewMode} onChange={setViewMode} />
      </div>

      {viewMode === 'executive' ? (
        <ExecutiveGrid themes={classifiedThemes} />
      ) : (
        <>
          <section className="px-6 py-2 md:px-10">
            <ThemeChart
              themes={classifiedThemes}
              selectedThemeId={selectedThemeId}
              onPointClick={setSelectedThemeId}
            />
          </section>
          <ThemeTable
            themes={classifiedThemes}
            selectedThemeId={selectedThemeId}
            onClearSelection={() => setSelectedThemeId(null)}
          />
        </>
      )}

      <ExcludedSection
        nonActionableThemes={nonActionableThemes}
        noiseCount={report.noiseCount}
        emptyMessageCount={report.emptyMessageCount}
      />
      <Footer generatedAt={report.generatedAt} />
    </div>
  )
}
