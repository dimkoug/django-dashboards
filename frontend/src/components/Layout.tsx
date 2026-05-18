import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { useAppDispatch, useAppSelector } from '../app/hooks'
import { logout } from '../features/auth/authSlice'
import { api, useLogoutServerMutation } from '../features/api/apiSlice'
import { useNotifications } from '../features/notifications/useNotifications'
import { NotificationBell } from './NotificationBell'

export function Layout() {
  const username = useAppSelector((s) => s.auth.username)
  const refresh = useAppSelector((s) => s.auth.refresh)
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [logoutServer] = useLogoutServerMutation()
  const [query, setQuery] = useState('')

  // Live assignment toasts over WebSocket while authenticated.
  useNotifications()

  const onSearch = (e: FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    if (q.length >= 2) navigate(`/search?q=${encodeURIComponent(q)}`)
  }

  const onLogout = async () => {
    // Blacklist the refresh token server-side (best-effort), then clear.
    if (refresh) {
      try {
        await logoutServer({ refresh }).unwrap()
      } catch {
        /* token already invalid / offline — clear locally anyway */
      }
    }
    dispatch(logout())
    dispatch(api.util.resetApiState())
    navigate('/login')
  }

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/my-todos" className="brand">
          Dashboard
        </Link>
        <nav className="nav">
          <NavLink to="/my-todos">My Todos</NavLink>
          <NavLink to="/dashboards">Dashboards</NavLink>
          <NavLink to="/account">Account</NavLink>
        </nav>
        <form className="topbar-search" onSubmit={onSearch}>
          <input
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </form>
        <div className="topbar-right">
          <NotificationBell />
          {username && <span className="user">{username}</span>}
          <button className="link-btn" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <ToastContainer position="bottom-right" theme="dark" />
    </div>
  )
}
