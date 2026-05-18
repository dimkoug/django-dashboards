import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useGetNotificationsQuery,
  useGetUnreadCountQuery,
  useMarkAllNotificationsReadMutation,
  useMarkNotificationReadMutation,
} from '../features/api/apiSlice'

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const { data: count } = useGetUnreadCountQuery(undefined, {
    pollingInterval: 60000,
  })
  const { data: items } = useGetNotificationsQuery(undefined, { skip: !open })
  const [markRead] = useMarkNotificationReadMutation()
  const [markAll] = useMarkAllNotificationsReadMutation()
  const navigate = useNavigate()
  const unread = count?.count ?? 0

  const onItem = async (id: number, link: string, read: boolean) => {
    if (!read) await markRead(id)
    setOpen(false)
    if (link) navigate(link)
  }

  return (
    <div className="bell-wrap">
      <button
        className="link-btn bell-btn"
        onClick={() => setOpen((o) => !o)}
        title="Notifications"
      >
        🔔
        {unread > 0 && <span className="bell-badge">{unread}</span>}
      </button>
      {open && (
        <div className="bell-menu">
          <div className="bell-head">
            <strong>Notifications</strong>
            <button className="link-btn" onClick={() => markAll()}>
              Mark all read
            </button>
          </div>
          <ul>
            {items?.slice(0, 20).map((n) => (
              <li
                key={n.id}
                className={n.read ? 'bell-item' : 'bell-item unread'}
                onClick={() => onItem(n.id, n.link, n.read)}
              >
                <span>{n.text}</span>
                <small className="dates">
                  {new Date(n.created_at).toLocaleString()}
                </small>
              </li>
            ))}
            {items && items.length === 0 && (
              <li className="bell-item dates">No notifications.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
