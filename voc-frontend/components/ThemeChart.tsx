'use client'

import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { statusColor } from '@/lib/statusColor'
import type { ClassifiedTheme } from '@/lib/types'

type Props = {
  themes: ClassifiedTheme[]
  selectedThemeId: number | null
  onPointClick: (themeId: number) => void
}

type ChartPoint = {
  id: number
  name: string
  x: number
  y: number
  z: number
  status: ClassifiedTheme['status']
}

export default function ThemeChart({ themes, selectedThemeId, onPointClick }: Props) {
  // Themes with no reliable trend (growthPercent === null) are excluded from
  // the chart entirely, matching report.py's `if growth is None: continue` —
  // plotting them at x=0 would misrepresent "unknown" as "flat."
  const data: ChartPoint[] = themes
    .filter((t): t is ClassifiedTheme & { growthPercent: number } => t.growthPercent !== null)
    .map((t) => ({
      id: t.id,
      name: t.name,
      x: t.growthPercent,
      y: t.severityPercentagePoints,
      z: t.ticketCount,
      status: t.status,
    }))

  return (
    <div>
      <p className="mb-2 text-xs text-[var(--text-dim)]">
        How to read this: each bubble is a theme — bubble size is ticket volume, position up
        means worse outcomes than baseline, position right means the theme is growing. Click a
        bubble to filter the table below to that theme.
      </p>
      <div className="h-80 w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 16, right: 24, bottom: 24, left: 8 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
            <XAxis
              type="number"
              dataKey="x"
              name="Growth"
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
              stroke="var(--border)"
              label={{
                value: 'More tickets over time →',
                position: 'insideBottom',
                offset: -12,
                fill: 'var(--text-dim)',
                fontSize: 12,
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="Severity"
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
              stroke="var(--border)"
              label={{
                value: '↑ Worse customer outcomes',
                angle: -90,
                position: 'insideLeft',
                fill: 'var(--text-dim)',
                fontSize: 12,
              }}
            />
            <ZAxis type="number" dataKey="z" range={[80, 800]} name="Tickets" />
            <Tooltip
              cursor={{ stroke: 'var(--border)' }}
              contentStyle={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                color: 'var(--text)',
                fontSize: 12,
              }}
              formatter={(value, name) => {
                // For ScatterChart, recharts passes each axis's configured
                // `name` prop here — not the underlying dataKey ('x'/'y'/'z').
                const num = typeof value === 'number' ? value : Number(value)
                if (name === 'Growth') return [`${num.toFixed(0)}%`, 'Growth']
                if (name === 'Severity') return [`${num.toFixed(1)} pts`, 'Severity']
                if (name === 'Tickets') return [num.toLocaleString(), 'Tickets']
                return [String(value), String(name)]
              }}
              labelFormatter={(_, payload) => payload?.[0]?.payload?.name ?? ''}
            />
            <Scatter
              data={data}
              onClick={(point) => {
                const id = (point as unknown as ChartPoint).id
                if (typeof id === 'number') onPointClick(id)
              }}
              cursor="pointer"
            >
              {data.map((point) => (
                <Cell
                  key={point.id}
                  fill={statusColor(point.status)}
                  stroke={point.id === selectedThemeId ? 'var(--text)' : 'none'}
                  strokeWidth={point.id === selectedThemeId ? 2 : 0}
                  fillOpacity={selectedThemeId === null || point.id === selectedThemeId ? 0.85 : 0.3}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
