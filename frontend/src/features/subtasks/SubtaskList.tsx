import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  useAddSubtaskMutation,
  useDeleteSubtaskMutation,
  useGetSubtasksQuery,
  useUpdateSubtaskMutation,
} from '../api/apiSlice'

export function SubtaskList({ todoId }: { todoId: number }) {
  const { data: subs, isLoading } = useGetSubtasksQuery(todoId)
  const [addSubtask] = useAddSubtaskMutation()
  const [updateSubtask] = useUpdateSubtaskMutation()
  const [deleteSubtask] = useDeleteSubtaskMutation()
  const [text, setText] = useState('')

  const onAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    await addSubtask({ todo: todoId, text: text.trim() })
    setText('')
  }

  const done = subs?.filter((s) => s.done).length ?? 0
  const total = subs?.length ?? 0

  return (
    <div className="comments">
      <h4>
        Checklist{' '}
        {total > 0 && (
          <span className="dates">
            {done}/{total}
          </span>
        )}
      </h4>
      {isLoading && <p className="dates">Loading…</p>}
      <ul className="comment-list">
        {subs?.map((s) => (
          <li key={s.id} className="subtask-row">
            <label className="check">
              <input
                type="checkbox"
                checked={s.done}
                onChange={(e) =>
                  updateSubtask({ id: s.id, done: e.target.checked })
                }
              />
              <span className={s.done ? 'done' : undefined}>{s.text}</span>
            </label>
            <button
              className="link-btn danger"
              title="Delete"
              onClick={() => deleteSubtask(s.id)}
            >
              ×
            </button>
          </li>
        ))}
        {total === 0 && <li className="dates">No checklist items.</li>}
      </ul>
      <form className="add-row" onSubmit={onAdd}>
        <input
          placeholder="Add checklist item…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>
    </div>
  )
}
