import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useGetDashboardStatsQuery,
  useGetDashboardsQuery,
  useLazyExportDashboardQuery,
} from '../features/api/apiSlice'

function Bar({
  label,
  value,
  max,
  cls,
}: {
  label: string
  value: number
  max: number
  cls?: string
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="stat-row">
      <span className="stat-label">{label}</span>
      <span className="stat-track">
        <span
          className={cls ? `stat-fill ${cls}` : 'stat-fill'}
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="stat-num">{value}</span>
    </div>
  )
}

export function StatsPage() {
  const { dashboardId } = useParams()
  const dId = Number(dashboardId)
  const { data: dashboards } = useGetDashboardsQuery()
  const { data: s, isLoading, isError } = useGetDashboardStatsQuery(dId)
  const [triggerExport] = useLazyExportDashboardQuery()
  const [exportErr, setExportErr] = useState<string | null>(null)

  const dash = dashboards?.find((d) => d.id === dId)

  const onExport = async (fmt: 'csv' | 'json') => {
    setExportErr(null)
    try {
      const blob = await triggerExport({ id: dId, fmt }).unwrap()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `dashboard-${dId}-todos.${fmt}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      setExportErr('Export failed.')
    }
  }

  if (isLoading) return <p>Loading…</p>
  if (isError || !s)
    return <p className="form-error">Failed to load stats.</p>

  const colMax = Math.max(1, ...s.by_column.map((c) => c.total))
  const asgMax = Math.max(1, ...s.by_assignee.map((a) => a.count))
  const prioMax = Math.max(
    1,
    s.by_priority.low,
    s.by_priority.medium,
    s.by_priority.high,
  )

  return (
    <section>
      <p className="crumbs">
        <Link to="/dashboards">Dashboards</Link> /{' '}
        <Link to={`/dashboards/${dId}`}>columns</Link> /{' '}
        {dash?.name ?? `Dashboard ${dId}`} stats
      </p>
      <h1>Analytics</h1>

      <div className="add-row">
        <button type="button" onClick={() => onExport('csv')}>
          Export CSV
        </button>
        <button type="button" onClick={() => onExport('json')}>
          Export JSON
        </button>
        {exportErr && <span className="form-error">{exportErr}</span>}
      </div>

      <div className="stat-tiles">
        <div className="tile">
          <div className="tile-num">{s.total}</div>
          <div className="tile-label">Total</div>
        </div>
        <div className="tile">
          <div className="tile-num">{s.open}</div>
          <div className="tile-label">Open</div>
        </div>
        <div className="tile">
          <div className="tile-num">{s.completed}</div>
          <div className="tile-label">Completed</div>
        </div>
        <div className="tile">
          <div className="tile-num overdue">{s.overdue}</div>
          <div className="tile-label">Overdue</div>
        </div>
      </div>

      <h2 className="section-title">By priority</h2>
      <Bar label="high" value={s.by_priority.high} max={prioMax}
           cls="prio-high" />
      <Bar label="medium" value={s.by_priority.medium} max={prioMax}
           cls="prio-medium" />
      <Bar label="low" value={s.by_priority.low} max={prioMax}
           cls="prio-low" />

      <h2 className="section-title">By column (completed / total)</h2>
      {s.by_column.map((c) => (
        <div key={c.id}>
          <Bar label={c.name} value={c.completed} max={colMax}
               cls="done-fill" />
          <Bar label="" value={c.total} max={colMax} />
        </div>
      ))}

      <h2 className="section-title">By assignee</h2>
      {s.by_assignee.length === 0 && (
        <p className="dates">No assignments.</p>
      )}
      {s.by_assignee.map((a) => (
        <Bar key={a.username} label={a.username} value={a.count}
             max={asgMax} />
      ))}
    </section>
  )
}
