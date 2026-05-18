import { useEffect, useRef } from 'react'
import { toast } from 'react-toastify'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { api, useCreateWsTicketMutation } from '../api/apiSlice'

type NotifyEvent =
  | { event: 'todo_assigned'; todo_id: number; todo_name: string }
  | { event: 'dashboard_shared'; dashboard_id: number; dashboard_name: string }
  | { event: 'comment_added'; todo_id: number; todo_name: string; actor: string }
  | { event: 'attachment_added'; todo_id: number; todo_name: string; actor: string }
  | { event: 'mentioned'; todo_id: number; todo_name: string; actor: string; comment_id: number }

/**
 * Opens a ticket-authenticated WebSocket to /ws/notifications/ while
 * logged in: mints a short-lived single-use ticket over HTTPS, then
 * connects with ?ticket= (no long-lived JWT in the URL). Reconnects
 * with backoff (fresh ticket each time); closes on logout/unmount.
 */
export function useNotifications() {
  const access = useAppSelector((s) => s.auth.access)
  const dispatch = useAppDispatch()
  const wsRef = useRef<WebSocket | null>(null)
  const [createTicket] = useCreateWsTicketMutation()

  useEffect(() => {
    if (!access) return

    let closedByUs = false
    let retry = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined

    const scheduleReconnect = () => {
      if (closedByUs) return
      const delay = Math.min(1000 * 2 ** retry, 30000)
      retry += 1
      reconnectTimer = setTimeout(connect, delay)
    }

    const connect = async () => {
      let ticket: string
      try {
        ticket = (await createTicket().unwrap()).ticket
      } catch {
        scheduleReconnect()
        return
      }
      if (closedByUs) return

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${window.location.host}/ws/notifications/?ticket=${ticket}`
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        retry = 0
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as NotifyEvent
          if (data.event === 'todo_assigned') {
            toast.info(`You were assigned to "${data.todo_name}"`)
            // Live-refresh the "My Todos" list.
            dispatch(
              api.util.invalidateTags([{ type: 'Todo', id: 'ASSIGNED' }]),
            )
          } else if (data.event === 'dashboard_shared') {
            toast.info(`"${data.dashboard_name}" was shared with you`)
            // The newly shared dashboard should appear in the list.
            dispatch(
              api.util.invalidateTags([{ type: 'Dashboard', id: 'LIST' }]),
            )
          } else if (data.event === 'comment_added') {
            toast.info(`${data.actor} commented on "${data.todo_name}"`)
            dispatch(
              api.util.invalidateTags([
                { type: 'Comment', id: 'LIST' },
                { type: 'Activity', id: 'LIST' },
              ]),
            )
          } else if (data.event === 'attachment_added') {
            toast.info(
              `${data.actor} attached a file to "${data.todo_name}"`,
            )
            dispatch(
              api.util.invalidateTags([
                { type: 'Attachment', id: 'LIST' },
                { type: 'Activity', id: 'LIST' },
              ]),
            )
          } else if (data.event === 'mentioned') {
            toast.info(
              `${data.actor} mentioned you in "${data.todo_name}"`,
            )
            dispatch(
              api.util.invalidateTags([{ type: 'Comment', id: 'LIST' }]),
            )
          }
          // Every recognised event is also persisted server-side —
          // refresh the bell.
          dispatch(
            api.util.invalidateTags([
              { type: 'Notification', id: 'LIST' },
              { type: 'Notification', id: 'COUNT' },
            ]),
          )
        } catch {
          /* ignore malformed frames */
        }
      }

      ws.onclose = () => {
        scheduleReconnect()
      }
    }

    connect()

    return () => {
      closedByUs = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
  }, [access, dispatch, createTicket])
}
