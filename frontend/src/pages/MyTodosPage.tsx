import { useGetAssignedTodosQuery } from '../features/api/apiSlice'
import type { Todo } from '../features/api/apiSlice'
import { dueBucket } from '../lib/due'
import type { DueBucket } from '../lib/due'

function fmt(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '—'
}

const SECTIONS: { key: DueBucket; label: string }[] = [
  { key: 'overdue', label: 'Overdue' },
  { key: 'soon', label: 'Due soon (7 days)' },
  { key: 'later', label: 'Later' },
  { key: 'completed', label: 'Completed' },
]

function Row({ t }: { t: Todo }) {
  const overdue = dueBucket(t) === 'overdue'
  return (
    <li className="todo-item">
      <span className={t.completed ? 'resource-name done' : 'resource-name'}>
        {t.name}
        <small className="dates">
          start {fmt(t.start_date)} · end {fmt(t.end_date)}
        </small>
      </span>
      <span
        className={
          overdue ? 'badge overdue' : t.completed ? 'badge done' : 'badge'
        }
      >
        {overdue ? 'overdue' : t.completed ? 'completed' : 'open'}
      </span>
    </li>
  )
}

export function MyTodosPage() {
  const { data: todos, isLoading, isError } = useGetAssignedTodosQuery()

  if (isLoading) return <p>Loading…</p>
  if (isError)
    return <p className="form-error">Failed to load assigned todos.</p>

  const grouped: Record<DueBucket, Todo[]> = {
    overdue: [],
    soon: [],
    later: [],
    completed: [],
  }
  for (const t of todos ?? []) grouped[dueBucket(t)].push(t)

  return (
    <section>
      <h1>My Todos</h1>
      <p className="crumbs">Todos assigned to you, grouped by due date.</p>

      {todos && todos.length === 0 && (
        <p className="empty">Nothing assigned to you yet.</p>
      )}

      {SECTIONS.map(({ key, label }) =>
        grouped[key].length > 0 ? (
          <div key={key} className="due-section">
            <h2 className={key === 'overdue' ? 'section-title overdue' : 'section-title'}>
              {label} <span className="count">{grouped[key].length}</span>
            </h2>
            <ul className="resource-list">
              {grouped[key].map((t) => (
                <Row key={t.id} t={t} />
              ))}
            </ul>
          </div>
        ) : null,
      )}
    </section>
  )
}
