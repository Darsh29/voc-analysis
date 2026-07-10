import ReportView from '@/components/ReportView'
import reportData from '../report-data.json'
import type { ReportData } from '@/lib/types'

export default function Home() {
  return <ReportView report={reportData as ReportData} />
}
