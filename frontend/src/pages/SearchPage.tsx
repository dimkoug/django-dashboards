import { Link, useSearchParams } from 'react-router-dom'
import { useGlobalSearchQuery } from '../features/api/apiSlice'

export function SearchPage() {
  const [params] = useSearchParams()
  const q = params.get('q') ?? ''
  const { data, isFetching } = useGlobalSearchQuery(q, {
    skip: q.trim().length < 2,
  })

  return (
    <section>
      <h1>Search</h1>
      <p className="crumbs">
        {q.trim().length < 2
          ? 'Type at least 2 characters in the search box.'
          : `Results for “${q}”`}
      </p>

      {isFetching && <p className="dates">Searching…</p>}

      {data && (
        <>
          <h2 className="section-title">
            Todos <span className="count">{data.todos.length}</span>
          </h2>
          <ul className="resource-list">
            {data.todos.map((t) => (
              <li key={t.id} className="todo-item">
                <Link
                  className="resource-name"
                  to={`/dashboards/${t.dashboard_id}/columns/${t.column}`}
                >
                  {t.name}
                </Link>
                <span className="dates">{t.dashboard_name}</span>
              </li>
            ))}
            {data.todos.length === 0 && (
              <li className="empty">No matching todos.</li>
            )}
          </ul>

          <h2 className="section-title">
            Comments <span className="count">{data.comments.length}</span>
          </h2>
          <ul className="resource-list">
            {data.comments.map((c) => (
              <li key={c.id} className="todo-item">
                <Link
                  className="resource-name"
                  to={`/dashboards/${c.dashboard_id}/columns/${c.column}`}
                >
                  {c.body}
                </Link>
                <span className="dates">
                  {c.author ?? 'someone'} · on “{c.todo_name}”
                </span>
              </li>
            ))}
            {data.comments.length === 0 && (
              <li className="empty">No matching comments.</li>
            )}
          </ul>
        </>
      )}
    </section>
  )
}
