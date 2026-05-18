import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useAddColumnMutation,
  useAddLabelMutation,
  useDeleteColumnMutation,
  useDeleteLabelMutation,
  useGetActivityQuery,
  useGetColumnsQuery,
  useGetDashboardsQuery,
  useGetLabelsQuery,
  useGetWebhooksQuery,
  useAddWebhookMutation,
  useDeleteWebhookMutation,
  useUpdateColumnMutation,
} from '../features/api/apiSlice'

const WEBHOOK_EVENTS = ['created', 'completed', 'moved'] as const

export function ColumnsPage() {
  const { dashboardId } = useParams()
  const dId = Number(dashboardId)

  const { data: dashboards } = useGetDashboardsQuery()
  const { data: activity } = useGetActivityQuery(dId)
  const { data: allColumns, isLoading, isError } = useGetColumnsQuery()
  const [addColumn] = useAddColumnMutation()
  const [updateColumn] = useUpdateColumnMutation()
  const [deleteColumn] = useDeleteColumnMutation()

  const { data: allLabels } = useGetLabelsQuery()
  const [addLabel] = useAddLabelMutation()
  const [deleteLabel] = useDeleteLabelMutation()

  const { data: allWebhooks } = useGetWebhooksQuery()
  const [addWebhook] = useAddWebhookMutation()
  const [deleteWebhook] = useDeleteWebhookMutation()
  const [hookUrl, setHookUrl] = useState('')
  const [hookEvents, setHookEvents] = useState<string[]>([])

  const [name, setName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [labelName, setLabelName] = useState('')
  const [labelColor, setLabelColor] = useState('#6366f1')

  const dashboard = dashboards?.find((d) => d.id === dId)
  // The API returns all of the user's columns; scope to this dashboard.
  const columns = allColumns?.filter((c) => c.dashboard === dId)
  const labels = allLabels?.filter((l) => l.dashboard === dId)
  const webhooks = allWebhooks?.filter((w) => w.dashboard === dId)

  const onAddWebhook = async (e: FormEvent) => {
    e.preventDefault()
    if (!hookUrl.trim()) return
    await addWebhook({
      dashboard: dId,
      url: hookUrl.trim(),
      events: hookEvents,
      active: true,
    })
    setHookUrl('')
    setHookEvents([])
  }

  const onAddLabel = async (e: FormEvent) => {
    e.preventDefault()
    if (!labelName.trim()) return
    await addLabel({
      dashboard: dId,
      name: labelName.trim(),
      color: labelColor,
    })
    setLabelName('')
  }

  const onAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    await addColumn({ dashboard: dId, name: name.trim() })
    setName('')
  }

  const onSaveEdit = async (id: number) => {
    await updateColumn({ id, name: editName.trim() })
    setEditingId(null)
  }

  if (isLoading) return <p>Loading…</p>
  if (isError) return <p className="form-error">Failed to load columns.</p>

  return (
    <section>
      <p className="crumbs">
        <Link to="/dashboards">Dashboards</Link> /{' '}
        {dashboard?.name ?? `Dashboard ${dId}`}
      </p>
      <h1>
        Columns{' '}
        <Link className="board-link" to={`/dashboards/${dId}/board`}>
          Board view →
        </Link>{' '}
        <Link className="board-link" to={`/dashboards/${dId}/stats`}>
          Analytics →
        </Link>
      </h1>

      <form className="add-row" onSubmit={onAdd}>
        <input
          placeholder="New column name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>

      <ul className="resource-list">
        {columns?.map((c) => (
          <li key={c.id}>
            {editingId === c.id ? (
              <>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                />
                <button onClick={() => onSaveEdit(c.id)}>Save</button>
                <button
                  className="link-btn"
                  onClick={() => setEditingId(null)}
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <Link
                  className="resource-name"
                  to={`/dashboards/${dId}/columns/${c.id}`}
                >
                  {c.name}
                </Link>
                <button
                  className="link-btn"
                  onClick={() => {
                    setEditingId(c.id)
                    setEditName(c.name)
                  }}
                >
                  Rename
                </button>
                <button
                  className="link-btn danger"
                  onClick={() => deleteColumn(c.id)}
                >
                  Delete
                </button>
              </>
            )}
          </li>
        ))}
        {columns?.length === 0 && <li className="empty">No columns yet.</li>}
      </ul>

      <h2 className="section-title">Labels</h2>
      <form className="add-row" onSubmit={onAddLabel}>
        <input
          placeholder="New label"
          value={labelName}
          onChange={(e) => setLabelName(e.target.value)}
        />
        <input
          type="color"
          value={labelColor}
          onChange={(e) => setLabelColor(e.target.value)}
          title="Label color"
        />
        <button type="submit">Add label</button>
      </form>
      <div className="label-chips">
        {labels?.map((l) => (
          <span
            key={l.id}
            className="chip"
            style={{ background: l.color }}
          >
            {l.name}
            <button
              className="chip-x"
              title="Delete label"
              onClick={() => deleteLabel(l.id)}
            >
              ×
            </button>
          </span>
        ))}
        {labels?.length === 0 && (
          <span className="dates">No labels yet.</span>
        )}
      </div>

      <h2 className="section-title">Activity</h2>
      <ul className="activity-feed">
        {activity?.slice(0, 30).map((a) => (
          <li key={a.id}>
            <strong>{a.actor_username ?? 'someone'}</strong> {a.message}
            <span className="dates">
              {' '}
              · {new Date(a.created_at).toLocaleString()}
            </span>
          </li>
        ))}
        {activity?.length === 0 && (
          <li className="dates">No activity yet.</li>
        )}
      </ul>

      {dashboard?.is_owner && (
        <>
          <h2 className="section-title">Webhooks</h2>
          <form className="add-row wrap" onSubmit={onAddWebhook}>
            <input
              placeholder="https://example.com/hook"
              value={hookUrl}
              onChange={(e) => setHookUrl(e.target.value)}
            />
            {WEBHOOK_EVENTS.map((ev) => (
              <label key={ev} className="check">
                <input
                  type="checkbox"
                  checked={hookEvents.includes(ev)}
                  onChange={(e) =>
                    setHookEvents((s) =>
                      e.target.checked
                        ? [...s, ev]
                        : s.filter((x) => x !== ev),
                    )
                  }
                />
                {ev}
              </label>
            ))}
            <button type="submit">Add webhook</button>
          </form>
          <ul className="resource-list">
            {webhooks?.map((w) => (
              <li key={w.id} className="todo-item">
                <span className="resource-name">{w.url}</span>
                <span className="dates">
                  {w.events.length ? w.events.join(', ') : 'all events'}
                </span>
                <button
                  className="link-btn danger"
                  onClick={() => deleteWebhook(w.id)}
                >
                  Delete
                </button>
              </li>
            ))}
            {webhooks?.length === 0 && (
              <li className="dates">No webhooks.</li>
            )}
          </ul>
        </>
      )}
    </section>
  )
}
