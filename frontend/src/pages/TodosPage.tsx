import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import Select from 'react-select'
import type { MultiValue, StylesConfig } from 'react-select'
import {
  useAddTodoMutation,
  useDeleteTodoMutation,
  useGetColumnsQuery,
  useGetLabelsQuery,
  useGetMeQuery,
  useGetTodosQuery,
  useUpdateTodoMutation,
  useGetSavedViewsQuery,
  useAddSavedViewMutation,
  useDeleteSavedViewMutation,
  useBulkTodosMutation,
} from '../features/api/apiSlice'
import type { Priority, Recurrence, Todo } from '../features/api/apiSlice'

const RECURRENCES: Recurrence[] = ['none', 'daily', 'weekly', 'monthly']
import { isOverdue } from '../lib/due'
import { CommentThread } from '../features/comments/CommentThread'
import { AttachmentList } from '../features/attachments/AttachmentList'
import { SubtaskList } from '../features/subtasks/SubtaskList'
import { AsyncUserSelect } from '../components/AsyncUserSelect'

const PRIORITIES: Priority[] = ['low', 'medium', 'high']

// ISO (UTC) -> value for <input type="datetime-local"> (local, no seconds).
function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(
    d.getHours(),
  )}:${p(d.getMinutes())}`
}

// datetime-local string -> ISO (UTC), or undefined when empty.
function fromLocalInput(local: string): string | undefined {
  return local ? new Date(local).toISOString() : undefined
}

function fmt(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '—'
}

// Turn an RTK Query error (DRF 400 body {field:[msgs]}) into a readable string.
function formatError(err: unknown): string {
  const data = (err as { data?: unknown }).data
  if (data && typeof data === 'object') {
    return Object.entries(data as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`)
      .join(' · ')
  }
  return 'Request failed.'
}

type Opt = { value: number; label: string }

// Dark-theme overrides so react-select matches the rest of the UI.
const selectStyles: StylesConfig<Opt, true> = {
  control: (b) => ({
    ...b,
    background: '#1e293b',
    borderColor: '#334155',
    minWidth: 220,
  }),
  menu: (b) => ({ ...b, background: '#1e293b' }),
  option: (b, s) => ({
    ...b,
    background: s.isFocused ? '#334155' : '#1e293b',
    color: '#e2e8f0',
  }),
  multiValue: (b) => ({ ...b, background: '#4f46e5' }),
  multiValueLabel: (b) => ({ ...b, color: '#fff' }),
  multiValueRemove: (b) => ({ ...b, color: '#e2e8f0' }),
  input: (b) => ({ ...b, color: '#e2e8f0' }),
  placeholder: (b) => ({ ...b, color: '#64748b' }),
}

export function TodosPage() {
  const { dashboardId, columnId } = useParams()
  const dId = Number(dashboardId)
  const cId = Number(columnId)

  const { data: columns } = useGetColumnsQuery()
  const { data: allTodos, isLoading, isError } = useGetTodosQuery()
  const { data: me } = useGetMeQuery()
  const { data: allLabels } = useGetLabelsQuery()
  const { data: savedViews } = useGetSavedViewsQuery()
  const [addSavedView] = useAddSavedViewMutation()
  const [deleteSavedView] = useDeleteSavedViewMutation()
  const [bulkTodos] = useBulkTodosMutation()
  const [selected, setSelected] = useState<number[]>([])
  const [addTodo] = useAddTodoMutation()
  const [updateTodo] = useUpdateTodoMutation()
  const [deleteTodo] = useDeleteTodoMutation()

  // Create form
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [recurrence, setRecurrence] = useState<Recurrence>('none')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [assignees, setAssignees] = useState<number[]>([])
  const [labelSel, setLabelSel] = useState<number[]>([])
  const [blockerSel, setBlockerSel] = useState<number[]>([])
  const [formKey, setFormKey] = useState(0)

  // Edit form
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editPriority, setEditPriority] = useState<Priority>('medium')
  const [editRecurrence, setEditRecurrence] = useState<Recurrence>('none')
  const [editStart, setEditStart] = useState('')
  const [editEnd, setEditEnd] = useState('')
  const [editCompleted, setEditCompleted] = useState(false)
  const [editAssignees, setEditAssignees] = useState<number[]>([])
  const [editLabels, setEditLabels] = useState<number[]>([])
  const [editBlockers, setEditBlockers] = useState<number[]>([])

  const [error, setError] = useState<string | null>(null)

  // Filter / sort bar (client-side over this column's todos)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<'all' | 'open' | 'done'>('all')
  const [mineOnly, setMineOnly] = useState(false)
  const [priorityFilter, setPriorityFilter] = useState<Priority | 'all'>('all')
  const [labelFilter, setLabelFilter] = useState<number | 'all'>('all')
  const [sortBy, setSortBy] = useState<'created' | 'end' | 'name'>('created')

  const column = columns?.find((c) => c.id === cId)
  const todos = allTodos?.filter((t) => t.column === cId)
  const visibleTodos = (todos ?? [])
    .filter((t) => !q || t.name.toLowerCase().includes(q.toLowerCase()))
    .filter((t) =>
      status === 'all' ? true : status === 'done' ? t.completed : !t.completed,
    )
    .filter((t) => !mineOnly || (!!me && t.users.includes(me.id)))
    .filter((t) => priorityFilter === 'all' || t.priority === priorityFilter)
    .filter((t) => labelFilter === 'all' || t.labels.includes(labelFilter))
    .slice()
    .sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name)
      if (sortBy === 'end') {
        const av = a.end_date ? new Date(a.end_date).getTime() : Infinity
        const bv = b.end_date ? new Date(b.end_date).getTime() : Infinity
        return av - bv
      }
      return b.id - a.id // newest first
    })
  // Other columns in THIS dashboard — valid move destinations.
  const moveTargets =
    columns?.filter((c) => c.dashboard === dId && c.id !== cId) ?? []

  // Labels are dashboard-scoped.
  const dashLabels = (allLabels ?? []).filter((l) => l.dashboard === dId)
  const labelOptions: Opt[] = dashLabels.map((l) => ({
    value: l.id,
    label: l.name,
  }))
  const labelOptsFor = (ids: number[]) =>
    labelOptions.filter((o) => ids.includes(o.value))
  const labelById = (id: number) => dashLabels.find((l) => l.id === id)

  // Blocker candidates: todos in this dashboard (any column).
  const dashColumnIds = new Set(
    (columns ?? []).filter((c) => c.dashboard === dId).map((c) => c.id),
  )
  const blockerOptionsExcl = (selfId?: number): Opt[] =>
    (allTodos ?? [])
      .filter((t) => dashColumnIds.has(t.column) && t.id !== selfId)
      .map((t) => ({ value: t.id, label: t.name }))
  const blockerOptsFor = (ids: number[]): Opt[] =>
    (allTodos ?? [])
      .filter((t) => ids.includes(t.id))
      .map((t) => ({ value: t.id, label: t.name }))

  const onAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setError(null)
    try {
      await addTodo({
        column: cId,
        name: name.trim(),
        description,
        priority,
        recurrence,
        users: assignees,
        labels: labelSel,
        blockers: blockerSel,
        // Omit start_date when blank so the server default (now) applies.
        start_date: fromLocalInput(start),
        end_date: fromLocalInput(end) ?? null,
      }).unwrap()
      setName('')
      setDescription('')
      setPriority('medium')
      setRecurrence('none')
      setStart('')
      setEnd('')
      setAssignees([])
      setLabelSel([])
      setBlockerSel([])
      setFormKey((k) => k + 1)
    } catch (err) {
      setError(formatError(err))
    }
  }

  const beginEdit = (t: Todo) => {
    setEditingId(t.id)
    setEditName(t.name)
    setEditDescription(t.description)
    setEditPriority(t.priority)
    setEditRecurrence(t.recurrence)
    setEditStart(toLocalInput(t.start_date))
    setEditEnd(toLocalInput(t.end_date))
    setEditCompleted(t.completed)
    setEditAssignees(t.users)
    setEditLabels(t.labels)
    setEditBlockers(t.blockers)
  }

  const onSaveEdit = async (id: number) => {
    setError(null)
    try {
      await updateTodo({
        id,
        name: editName.trim(),
        description: editDescription,
        priority: editPriority,
        recurrence: editRecurrence,
        users: editAssignees,
        labels: editLabels,
        blockers: editBlockers,
        start_date: fromLocalInput(editStart),
        // Empty edit field clears end_date (null), not "leave unchanged".
        end_date: fromLocalInput(editEnd) ?? null,
        completed: editCompleted,
      }).unwrap()
      setEditingId(null)
    } catch (err) {
      setError(formatError(err))
    }
  }

  const currentViewParams = () => ({
    q,
    status,
    mineOnly,
    priorityFilter,
    labelFilter,
    sortBy,
  })

  const applyView = (p: Record<string, unknown>) => {
    if (typeof p.q === 'string') setQ(p.q)
    if (p.status === 'all' || p.status === 'open' || p.status === 'done')
      setStatus(p.status)
    if (typeof p.mineOnly === 'boolean') setMineOnly(p.mineOnly)
    if (p.priorityFilter === 'all' || p.priorityFilter === 'low' ||
        p.priorityFilter === 'medium' || p.priorityFilter === 'high')
      setPriorityFilter(p.priorityFilter)
    if (p.labelFilter === 'all' || typeof p.labelFilter === 'number')
      setLabelFilter(p.labelFilter)
    if (p.sortBy === 'created' || p.sortBy === 'end' || p.sortBy === 'name')
      setSortBy(p.sortBy)
  }

  const saveCurrentView = async () => {
    const name = window.prompt('Save current filters as:')
    if (name && name.trim()) {
      await addSavedView({ name: name.trim(), params: currentViewParams() })
    }
  }

  const toggleSelect = (id: number) =>
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id],
    )

  const runBulk = async (
    action: 'complete' | 'reopen' | 'move' | 'label_add' | 'delete',
    value?: number,
  ) => {
    if (selected.length === 0) return
    if (action === 'delete' && !window.confirm(`Delete ${selected.length}?`))
      return
    setError(null)
    try {
      await bulkTodos({ ids: selected, action, value }).unwrap()
      setSelected([])
    } catch (err) {
      setError(formatError(err))
    }
  }

  if (isLoading) return <p>Loading…</p>
  if (isError) return <p className="form-error">Failed to load todos.</p>

  return (
    <section>
      <p className="crumbs">
        <Link to="/dashboards">Dashboards</Link> /{' '}
        <Link to={`/dashboards/${dId}`}>columns</Link> /{' '}
        {column?.name ?? `Column ${cId}`}
      </p>
      <h1>Todos</h1>

      <form className="add-row wrap" onSubmit={onAdd}>
        <input
          placeholder="New todo"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label className="field">
          Priority
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Repeat
          <select
            value={recurrence}
            onChange={(e) => setRecurrence(e.target.value as Recurrence)}
          >
            {RECURRENCES.map((rr) => (
              <option key={rr} value={rr}>
                {rr}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Labels
          <Select<Opt, true>
            isMulti
            options={labelOptions}
            value={labelOptsFor(labelSel)}
            onChange={(v: MultiValue<Opt>) =>
              setLabelSel(v.map((o) => o.value))
            }
            styles={selectStyles}
            placeholder="Labels…"
          />
        </label>
        <label className="field">
          Blocked by
          <Select<Opt, true>
            isMulti
            options={blockerOptionsExcl()}
            value={blockerOptsFor(blockerSel)}
            onChange={(v: MultiValue<Opt>) =>
              setBlockerSel(v.map((o) => o.value))
            }
            styles={selectStyles}
            placeholder="Blockers…"
          />
        </label>
        <label className="field">
          Start
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label className="field">
          End
          <input
            type="datetime-local"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label className="field">
          Assignees
          <AsyncUserSelect
            key={`new-${formKey}`}
            initial={[]}
            onChange={setAssignees}
            placeholder="Assign users…"
          />
        </label>
        <textarea
          className="desc-input"
          placeholder="Description (markdown)…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>

      {error && <p className="form-error">{error}</p>}

      <div className="filter-bar">
        <input
          placeholder="Search…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          value={status}
          onChange={(e) =>
            setStatus(e.target.value as 'all' | 'open' | 'done')
          }
        >
          <option value="all">All</option>
          <option value="open">Open</option>
          <option value="done">Completed</option>
        </select>
        <label className="check">
          <input
            type="checkbox"
            checked={mineOnly}
            onChange={(e) => setMineOnly(e.target.checked)}
          />
          Assigned to me
        </label>
        <select
          value={priorityFilter}
          onChange={(e) =>
            setPriorityFilter(e.target.value as Priority | 'all')
          }
        >
          <option value="all">Any priority</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={String(labelFilter)}
          onChange={(e) =>
            setLabelFilter(
              e.target.value === 'all' ? 'all' : Number(e.target.value),
            )
          }
        >
          <option value="all">Any label</option>
          {dashLabels.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) =>
            setSortBy(e.target.value as 'created' | 'end' | 'name')
          }
        >
          <option value="created">Newest</option>
          <option value="end">Due date</option>
          <option value="name">Name</option>
        </select>
      </div>

      <div className="saved-views">
        <span className="dates">Views:</span>
        {savedViews?.map((v) => (
          <span key={v.id} className="chip view-chip">
            <button
              className="chip-apply"
              onClick={() => applyView(v.params)}
            >
              {v.name}
            </button>
            <button
              className="chip-x"
              title="Delete view"
              onClick={() => deleteSavedView(v.id)}
            >
              ×
            </button>
          </span>
        ))}
        <button className="link-btn" onClick={saveCurrentView}>
          + Save view
        </button>
      </div>

      {selected.length > 0 && (
        <div className="bulk-bar">
          <span>{selected.length} selected</span>
          <button onClick={() => runBulk('complete')}>Complete</button>
          <button onClick={() => runBulk('reopen')}>Reopen</button>
          {moveTargets.length > 0 && (
            <select
              value=""
              onChange={(e) =>
                runBulk('move', Number(e.target.value))
              }
            >
              <option value="" disabled>
                Move to…
              </option>
              {moveTargets.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          {dashLabels.length > 0 && (
            <select
              value=""
              onChange={(e) =>
                runBulk('label_add', Number(e.target.value))
              }
            >
              <option value="" disabled>
                Add label…
              </option>
              {dashLabels.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          )}
          <button className="link-btn danger"
                  onClick={() => runBulk('delete')}>
            Delete
          </button>
          <button className="link-btn" onClick={() => setSelected([])}>
            Clear
          </button>
        </div>
      )}

      <ul className="resource-list">
        {visibleTodos.map((t) => (
          <li key={t.id} className="todo-item">
            {editingId === t.id ? (
              <div className="edit-grid">
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                />
                <label className="field">
                  Priority
                  <select
                    value={editPriority}
                    onChange={(e) =>
                      setEditPriority(e.target.value as Priority)
                    }
                  >
                    {PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Repeat
                  <select
                    value={editRecurrence}
                    onChange={(e) =>
                      setEditRecurrence(e.target.value as Recurrence)
                    }
                  >
                    {RECURRENCES.map((rr) => (
                      <option key={rr} value={rr}>
                        {rr}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Labels
                  <Select<Opt, true>
                    isMulti
                    options={labelOptions}
                    value={labelOptsFor(editLabels)}
                    onChange={(v: MultiValue<Opt>) =>
                      setEditLabels(v.map((o) => o.value))
                    }
                    styles={selectStyles}
                    placeholder="Labels…"
                  />
                </label>
                <label className="field">
                  Blocked by
                  <Select<Opt, true>
                    isMulti
                    options={blockerOptionsExcl(t.id)}
                    value={blockerOptsFor(editBlockers)}
                    onChange={(v: MultiValue<Opt>) =>
                      setEditBlockers(v.map((o) => o.value))
                    }
                    styles={selectStyles}
                    placeholder="Blockers…"
                  />
                </label>
                <label className="field">
                  Start
                  <input
                    type="datetime-local"
                    value={editStart}
                    onChange={(e) => setEditStart(e.target.value)}
                  />
                </label>
                <label className="field">
                  End
                  <input
                    type="datetime-local"
                    value={editEnd}
                    onChange={(e) => setEditEnd(e.target.value)}
                  />
                </label>
                <label className="field">
                  Assignees
                  <AsyncUserSelect
                    key={`edit-${t.id}`}
                    initial={t.assignees}
                    onChange={setEditAssignees}
                    placeholder="Assign users…"
                  />
                </label>
                <textarea
                  className="desc-input"
                  placeholder="Description (markdown)…"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
                <label className="check">
                  <input
                    type="checkbox"
                    checked={editCompleted}
                    onChange={(e) => setEditCompleted(e.target.checked)}
                  />
                  Completed
                </label>
                <div className="edit-actions">
                  <button onClick={() => onSaveEdit(t.id)}>Save</button>
                  <button
                    className="link-btn"
                    onClick={() => setEditingId(null)}
                  >
                    Cancel
                  </button>
                </div>
                <SubtaskList todoId={t.id} />
                <AttachmentList todoId={t.id} />
                <CommentThread todoId={t.id} />
              </div>
            ) : (
              <>
                <input
                  type="checkbox"
                  className="bulk-check"
                  checked={selected.includes(t.id)}
                  onChange={() => toggleSelect(t.id)}
                />
                <span
                  className={
                    t.completed ? 'resource-name done' : 'resource-name'
                  }
                >
                  {t.name}
                  <span className={`badge prio-${t.priority}`}>
                    {t.priority}
                  </span>
                  {t.recurrence !== 'none' && (
                    <span className="badge">↻ {t.recurrence}</span>
                  )}
                  {t.blockers_open > 0 && (
                    <span className="badge overdue">
                      ⛓ {t.blockers_open}
                    </span>
                  )}
                  {isOverdue(t) && (
                    <span className="badge overdue">overdue</span>
                  )}
                  {t.labels.map((id) => {
                    const l = labelById(id)
                    return l ? (
                      <span
                        key={id}
                        className="chip"
                        style={{ background: l.color }}
                      >
                        {l.name}
                      </span>
                    ) : null
                  })}
                  <small className="dates">
                    start {fmt(t.start_date)} · end {fmt(t.end_date)}
                    {t.assignees.length > 0 && (
                      <> · 👤 {t.assignees.map((a) => a.username).join(', ')}</>
                    )}
                    {t.subtask_summary.total > 0 && (
                      <>
                        {' '}
                        · ☑ {t.subtask_summary.done}/
                        {t.subtask_summary.total}
                      </>
                    )}
                  </small>
                  {t.description_html && (
                    <small
                      className="desc-html"
                      dangerouslySetInnerHTML={{
                        __html: t.description_html,
                      }}
                    />
                  )}
                </span>
                <button
                  className="link-btn"
                  onClick={() =>
                    updateTodo({ id: t.id, completed: !t.completed })
                  }
                >
                  {t.completed ? 'Reopen' : 'Complete'}
                </button>
                {moveTargets.length > 0 && (
                  <select
                    className="move-select"
                    value=""
                    onChange={(e) =>
                      updateTodo({
                        id: t.id,
                        column: Number(e.target.value),
                      })
                    }
                  >
                    <option value="" disabled>
                      Move to…
                    </option>
                    {moveTargets.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  className="link-btn"
                  onClick={() => beginEdit(t)}
                >
                  Edit
                </button>
                <button
                  className="link-btn danger"
                  onClick={() => deleteTodo(t.id)}
                >
                  Delete
                </button>
              </>
            )}
          </li>
        ))}
        {visibleTodos.length === 0 && (
          <li className="empty">
            {todos && todos.length > 0
              ? 'No todos match the filters.'
              : 'No todos yet.'}
          </li>
        )}
      </ul>
    </section>
  )
}
