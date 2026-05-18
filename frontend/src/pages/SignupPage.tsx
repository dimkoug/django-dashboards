import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAppDispatch } from '../app/hooks'
import {
  useLoginMutation,
  useRegisterMutation,
} from '../features/api/apiSlice'
import { setCredentials } from '../features/auth/authSlice'

// Turn a DRF 400 body ({field: [msgs]}) into a readable string.
function formatError(data: unknown): string {
  if (data && typeof data === 'object') {
    return Object.entries(data as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`)
      .join(' · ')
  }
  return 'Registration failed.'
}

export function SignupPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [register, { isLoading }] = useRegisterMutation()
  const [login] = useLoginMutation()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await register({ username, email, password }).unwrap()
      // Auto-login right after a successful registration.
      const tokens = await login({ username, password }).unwrap()
      dispatch(setCredentials({ ...tokens, username }))
      navigate('/my-todos', { replace: true })
    } catch (err) {
      const data = (err as { data?: unknown }).data
      setError(formatError(data))
    }
  }

  return (
    <div className="auth-card">
      <h1>Sign up</h1>
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
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Creating account…' : 'Sign up'}
        </button>
      </form>
      <p className="auth-alt">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  )
}
