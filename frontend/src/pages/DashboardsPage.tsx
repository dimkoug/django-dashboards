import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  useAddDashboardMutation,
  useDeleteDashboardMutation,
  useGetDashboardsQuery,
  useUpdateDashboardMutation,
} from '../features/api/apiSlice'
import { AsyncUserSelect } from '../components/AsyncUserSelect'

export function DashboardsPage() {
  const { data: dashboards, isLoading, isError } = useGetDashboardsQuery()
  const [addDashboard] = useAddDashboardMutation()
  const [updateDashboard] = useUpdateDashboardMutation()
  const [deleteDashboard] = useDeleteDashboardMutation()

  const [name, setName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')

  const onAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    await addDashboard({ name: name.trim() })
    setName('')
  }

  const onSaveEdit = async (id: number) => {
    await updateDashboard({ id, name: editName.trim() })
    setEditingId(null)
  }

  if (isLoading) return <p>Loading…</p>
  if (isError) return <p className="form-error">Failed to load dashboards.</p>

  return (
    <section>
      <h1>Dashboards</h1>

      <form className="add-row" onSubmit={onAdd}>
        <input
          placeholder="New dashboard name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>

      <ul className="resource-list">
        {dashboards?.map((d) => (
          <li key={d.id} className="todo-item">
            {editingId === d.id ? (
              <>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                />
                <button onClick={() => onSaveEdit(d.id)}>Save</button>
                <button
                  className="link-btn"
                  onClick={() => setEditingId(null)}
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <Link className="resource-name" to={`/dashboards/${d.id}`}>
                  {d.name}
                </Link>
                <span className={d.is_owner ? 'badge' : 'badge done'}>
                  {d.is_owner ? 'owner' : 'shared'}
                </span>

                {d.is_owner ? (
                  <>
                    <label className="field">
                      Share with
                      <AsyncUserSelect
                        initial={d.members}
                        onChange={(ids) =>
                          updateDashboard({ id: d.id, users: ids })
                        }
                        placeholder="Add members…"
                      />
                    </label>
                    <button
                      className="link-btn"
                      onClick={() => {
                        setEditingId(d.id)
                        setEditName(d.name)
                      }}
                    >
                      Rename
                    </button>
                    <button
                      className="link-btn danger"
                      onClick={() => deleteDashboard(d.id)}
                    >
                      Delete
                    </button>
                  </>
                ) : (
                  <span className="dates">shared with you</span>
                )}
              </>
            )}
          </li>
        ))}
        {dashboards?.length === 0 && (
          <li className="empty">No dashboards yet.</li>
        )}
      </ul>
    </section>
  )
}
