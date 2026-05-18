import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  useAddCommentMutation,
  useDeleteCommentMutation,
  useGetCommentsQuery,
} from '../api/apiSlice'

// Wrap @mentions in a highlight span.
function renderBody(body: string): ReactNode[] {
  return body.split(/(@[\w.-]+)/g).map((part, i) =>
    /^@[\w.-]+$/.test(part) ? (
      <span key={i} className="mention">
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    ),
  )
}

export function CommentThread({ todoId }: { todoId: number }) {
  const { data: comments, isLoading } = useGetCommentsQuery(todoId)
  const [addComment] = useAddCommentMutation()
  const [deleteComment] = useDeleteCommentMutation()
  const [body, setBody] = useState('')

  const onAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!body.trim()) return
    await addComment({ todo: todoId, body: body.trim() })
    setBody('')
  }

  return (
    <div className="comments">
      <h4>Comments</h4>
      {isLoading && <p className="dates">Loading…</p>}
      <ul className="comment-list">
        {comments?.map((c) => (
          <li key={c.id}>
            <div>
              <strong>{c.author_username}</strong>{' '}
              <span className="dates">
                {new Date(c.created_at).toLocaleString()}
              </span>
              <button
                className="link-btn danger"
                onClick={() => deleteComment(c.id)}
                title="Delete comment"
              >
                ×
              </button>
            </div>
            <div className="comment-body">{renderBody(c.body)}</div>
          </li>
        ))}
        {comments?.length === 0 && (
          <li className="dates">No comments yet.</li>
        )}
      </ul>
      <form className="add-row" onSubmit={onAdd}>
        <input
          placeholder="Add a comment…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <button type="submit">Comment</button>
      </form>
    </div>
  )
}
