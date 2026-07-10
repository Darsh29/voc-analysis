'use client'

import { Line, LineChart, ResponsiveContainer } from 'recharts'
import type { DailyVolume } from '@/lib/types'

type Props = {
  dailyVolume: DailyVolume[]
  color: string
}

export default function Sparkline({ dailyVolume, color }: Props) {
  return (
    <div style={{ width: 80, height: 28 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={dailyVolume} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <Line
            type="monotone"
            dataKey="count"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
