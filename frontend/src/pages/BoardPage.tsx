import type { CSSProperties } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  DndContext,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent } from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { useAppDispatch } from '../app/hooks'
import {
  api,
  useGetColumnsQuery,
  useGetDashboardsQuery,
  useGetLabelsQuery,
  useGetTodosQuery,
  useReorderTodosMutation,
  useUpdateTodoMutation,
} from '../features/api/apiSlice'
import type { Column, Label, Todo } from '../features/api/apiSlice'
import { isOverdue } from '../lib/due'

function fmt(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString() : '—'
}

const byPos = (a: Todo, b: Todo) => a.position - b.position || a.id - b.id

function Card({
  todo,
  labels,
}: {
  todo: Todo
  labels: Label[]
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: todo.id })
  const style: CSSProperties = {
    transform: transform
      ? `translate3d(${transform.x}px, ${transform.y}px, 0)`
      : undefined,
    transition,
    opacity: isDragging ? 0.4 : 1,
  }
  const overdue = isOverdue(todo)
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={overdue ? 'kanban-card overdue' : 'kanban-card'}
      {...listeners}
      {...attributes}
    >
      <span className={todo.completed ? 'card-title done' : 'card-title'}>
        {todo.name}
      </span>
      <div className="card-tags">
        <span className={`badge prio-${todo.priority}`}>{todo.priority}</span>
        {todo.labels.map((id) => {
          const l = labels.find((x) => x.id === id)
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
      </div>
      <small className="card-meta">
        ends {fmt(todo.end_date)}
        {overdue && ' · overdue'}
        {todo.users.length > 0 && ` · 👤 ${todo.users.length}`}
        {todo.subtask_summary.total > 0 &&
          ` · ☑ ${todo.subtask_summary.done}/${todo.subtask_summary.total}`}
        {todo.recurrence !== 'none' && ` · ↻ ${todo.recurrence}`}
        {todo.blockers_open > 0 && ` · ⛓ ${todo.blockers_open}`}
      </small>
    </div>
  )
}

function Lane({
  column,
  items,
  labels,
}: {
  column: Column
  items: Todo[]
  labels: Label[]
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `col-${column.id}` })
  return (
    <div
      ref={setNodeRef}
      className={isOver ? 'kanban-lane over' : 'kanban-lane'}
    >
      <h3>
        {column.name} <span className="count">{items.length}</span>
      </h3>
      <SortableContext
        items={items.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="kanban-cards">
          {items.map((t) => (
            <Card key={t.id} todo={t} labels={labels} />
          ))}
          {items.length === 0 && <p className="empty-lane">Drop here</p>}
        </div>
      </SortableContext>
    </div>
  )
}

export function BoardPage() {
  const { dashboardId } = useParams()
  const dId = Number(dashboardId)

  const { data: dashboards } = useGetDashboardsQuery()
  const { data: columns } = useGetColumnsQuery()
  const { data: todos } = useGetTodosQuery()
  const { data: allLabels } = useGetLabelsQuery()
  const [updateTodo] = useUpdateTodoMutation()
  const [reorderTodos] = useReorderTodosMutation()
  const dispatch = useAppDispatch()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  )

  const dash = dashboards?.find((d) => d.id === dId)
  const lanes = (columns ?? []).filter((c) => c.dashboard === dId)
  const labels = (allLabels ?? []).filter((l) => l.dashboard === dId)
  const inColumn = (cid: number) =>
    (todos ?? []).filter((t) => t.column === cid).slice().sort(byPos)

  const onDragEnd = async (e: DragEndEvent) => {
    if (!e.over || !todos) return
    const activeId = Number(e.active.id)
    const todo = todos.find((t) => t.id === activeId)
    if (!todo) return

    const overId = e.over.id
    let targetCol: number
    let overTodo: Todo | undefined
    if (typeof overId === 'string' && overId.startsWith('col-')) {
      targetCol = Number(overId.slice(4))
    } else {
      overTodo = todos.find((t) => t.id === Number(overId))
      if (!overTodo) return
      targetCol = overTodo.column
    }
    const sourceCol = todo.column

    // New ordered id list for the target column.
    const targetIds = inColumn(targetCol)
      .filter((t) => t.id !== activeId)
      .map((t) => t.id)
    let insertAt = targetIds.length
    if (overTodo) {
      const idx = targetIds.indexOf(overTodo.id)
      insertAt = idx === -1 ? targetIds.length : idx
    }
    targetIds.splice(insertAt, 0, activeId)

    if (
      sourceCol === targetCol &&
      targetIds.join() === inColumn(targetCol).map((t) => t.id).join()
    ) {
      return // no change
    }

    // Optimistic: move + re-sequence affected lanes in the cache.
    const patch = dispatch(
      api.util.updateQueryData('getTodos', undefined, (draft) => {
        const moved = draft.find((t) => t.id === activeId)
        if (moved) moved.column = targetCol
        targetIds.forEach((id, i) => {
          const d = draft.find((t) => t.id === id)
          if (d) d.position = i
        })
        if (sourceCol !== targetCol) {
          draft
            .filter((t) => t.column === sourceCol)
            .sort(byPos)
            .forEach((t, i) => {
              t.position = i
            })
        }
      }),
    )

    try {
      if (sourceCol !== targetCol) {
        await updateTodo({ id: activeId, column: targetCol }).unwrap()
      }
      await reorderTodos({ column: targetCol, order: targetIds }).unwrap()
    } catch {
      patch.undo()
    }
  }

  if (!columns || !todos) return <p>Loading…</p>

  return (
    <section>
      <p className="crumbs">
        <Link to="/dashboards">Dashboards</Link> /{' '}
        <Link to={`/dashboards/${dId}`}>columns</Link> /{' '}
        {dash?.name ?? `Dashboard ${dId}`} board
      </p>
      <h1>Board</h1>

      {lanes.length === 0 ? (
        <p className="empty">No columns in this dashboard yet.</p>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragEnd={onDragEnd}
        >
          <div className="kanban">
            {lanes.map((c) => (
              <Lane
                key={c.id}
                column={c}
                items={inColumn(c.id)}
                labels={labels}
              />
            ))}
          </div>
        </DndContext>
      )}
    </section>
  )
}
