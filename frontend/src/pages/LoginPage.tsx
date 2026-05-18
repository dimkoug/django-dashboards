import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAppDispatch } from '../app/hooks'
import { useLoginMutation } from '../features/api/apiSlice'
import { setCredentials } from '../features/auth/authSlice'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [login, { isLoading }] = useLoginMutation()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)

  const from =
    (location.state as { from?: { pathname: string } } | null)?.from
      ?.pathname ?? '/my-todos'

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const tokens = await login({ username, password }).unwrap()
      dispatch(setCredentials({ ...tokens, username }))
      navigate(from, { replace: true })
    } catch {
      setError('Invalid username or password.')
    }
  }

  return (
    <div className="auth-card">
      <h1>Log in</h1>
      <form onSubmit={onSubmit}>
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Signing in…' : 'Log in'}
        </button>
      </form>
      <p className="auth-alt">
        No account? <Link to="/signup">Sign up</Link>
      </p>
    </div>
  )
}
