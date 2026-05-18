import type { Todo } from '../features/api/apiSlice'

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

/** Open todo whose end_date is in the past. */
export function isOverdue(t: Pick<Todo, 'completed' | 'end_date'>): boolean {
  return !t.completed && !!t.end_date && new Date(t.end_date).getTime() < Date.now()
}

export type DueBucket = 'completed' | 'overdue' | 'soon' | 'later'

/** Bucket a todo for the "My Todos" grouped view. */
export function dueBucket(t: Todo): DueBucket {
  if (t.completed) return 'completed'
  if (!t.end_date) return 'later'
  const ms = new Date(t.end_date).getTime()
  const now = Date.now()
  if (ms < now) return 'overdue'
  if (ms <= now + WEEK_MS) return 'soon'
  return 'later'
}
