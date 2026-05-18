import { useRef, useState } from 'react'
import {
  useAddAttachmentMutation,
  useDeleteAttachmentMutation,
  useGetAttachmentsQuery,
} from '../api/apiSlice'

function humanSize(n: number | null): string {
  if (n == null) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export function AttachmentList({ todoId }: { todoId: number }) {
  const { data: files, isLoading } = useGetAttachmentsQuery(todoId)
  const [addAttachment, { isLoading: uploading }] = useAddAttachmentMutation()
  const [deleteAttachment] = useDeleteAttachmentMutation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    try {
      await addAttachment({ todo: todoId, file }).unwrap()
    } catch {
      setError('Upload failed.')
    } finally {
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="comments">
      <h4>Attachments</h4>
      {isLoading && <p className="dates">Loading…</p>}
      <ul className="comment-list">
        {files?.map((f) => (
          <li key={f.id}>
            <a href={f.file_url} target="_blank" rel="noreferrer">
              {f.original_name}
            </a>{' '}
            <span className="dates">
              {humanSize(f.size)} · {f.uploaded_by_username ?? 'someone'}
            </span>
            <button
              className="link-btn danger"
              title="Delete attachment"
              onClick={() => deleteAttachment(f.id)}
            >
              ×
            </button>
          </li>
        ))}
        {files?.length === 0 && (
          <li className="dates">No attachments yet.</li>
        )}
      </ul>
      <input
        ref={inputRef}
        type="file"
        onChange={onPick}
        disabled={uploading}
      />
      {uploading && <span className="dates"> uploading…</span>}
      {error && <p className="form-error">{error}</p>}
    </div>
  )
}
