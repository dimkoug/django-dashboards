import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  useChangePasswordMutation,
  useGetCalendarFeedQuery,
  useGetMeQuery,
  useGetPreferencesQuery,
  useRegenerateCalendarFeedMutation,
  useUpdateMeMutation,
  useUpdatePreferencesMutation,
} from '../features/api/apiSlice'
import type { ThemePref } from '../features/api/apiSlice'
import { applyTheme } from '../lib/theme'

function formatError(err: unknown): string {
  const data = (err as { data?: unknown }).data
  if (data && typeof data === 'object') {
    return Object.entries(data as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`)
      .join(' · ')
  }
  return 'Request failed.'
}

export function AccountPage() {
  const { data: me, isLoading } = useGetMeQuery()
  const [updateMe] = useUpdateMeMutation()
  const [changePassword] = useChangePasswordMutation()
  const { data: feed } = useGetCalendarFeedQuery()
  const [regenFeed] = useRegenerateCalendarFeedMutation()
  const { data: prefs } = useGetPreferencesQuery()
  const [updatePrefs] = useUpdatePreferencesMutation()
  const feedUrl = feed ? window.location.origin + feed.path : ''

  const [email, setEmail] = useState('')
  const [profileMsg, setProfileMsg] = useState<string | null>(null)

  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwMsg, setPwMsg] = useState<string | null>(null)
  const [pwErr, setPwErr] = useState<string | null>(null)

  useEffect(() => {
    if (me) setEmail(me.email)
  }, [me])

  if (isLoading) return <p>Loading…</p>

  const onSaveProfile = async (e: FormEvent) => {
    e.preventDefault()
    setProfileMsg(null)
    try {
      await updateMe({ email }).unwrap()
      setProfileMsg('Saved.')
    } catch (err) {
      setProfileMsg(formatError(err))
    }
  }

  const onChangePassword = async (e: FormEvent) => {
    e.preventDefault()
    setPwMsg(null)
    setPwErr(null)
    try {
      await changePassword({
        old_password: oldPw,
        new_password: newPw,
      }).unwrap()
      setPwMsg('Password changed.')
      setOldPw('')
      setNewPw('')
    } catch (err) {
      setPwErr(formatError(err))
    }
  }

  return (
    <section>
      <h1>Account</h1>
      <p className="crumbs">
        Signed in as <strong>{me?.username}</strong>
      </p>

      <h2 className="section-title">Profile</h2>
      <form className="add-row" onSubmit={onSaveProfile}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button type="submit">Save</button>
      </form>
      {profileMsg && <p className="dates">{profileMsg}</p>}

      <h2 className="section-title">Change password</h2>
      <form className="auth-card-inline" onSubmit={onChangePassword}>
        <input
          type="password"
          placeholder="Current password"
          value={oldPw}
          autoComplete="current-password"
          onChange={(e) => setOldPw(e.target.value)}
        />
        <input
          type="password"
          placeholder="New password"
          value={newPw}
          autoComplete="new-password"
          onChange={(e) => setNewPw(e.target.value)}
        />
        <button type="submit">Change password</button>
      </form>
      {pwMsg && <p className="dates">{pwMsg}</p>}
      {pwErr && <p className="form-error">{pwErr}</p>}

      <h2 className="section-title">Email notifications</h2>
      <label className="check">
        <input
          type="checkbox"
          checked={prefs?.email_on_assign ?? true}
          onChange={(e) =>
            updatePrefs({ email_on_assign: e.target.checked })
          }
        />
        Email me when I'm assigned a todo
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={prefs?.email_on_mention ?? true}
          onChange={(e) =>
            updatePrefs({ email_on_mention: e.target.checked })
          }
        />
        Email me when I'm @mentioned
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={prefs?.email_on_due ?? true}
          onChange={(e) => updatePrefs({ email_on_due: e.target.checked })}
        />
        Email me when a todo is overdue or due soon
      </label>

      <h2 className="section-title">Appearance</h2>
      <label className="check">
        Theme
        <select
          className="move-select"
          value={prefs?.theme ?? 'system'}
          onChange={(e) => {
            const theme = e.target.value as ThemePref
            applyTheme(theme) // instant, no wait for the round-trip
            updatePrefs({ theme })
          }}
        >
          <option value="system">System</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </label>

      <h2 className="section-title">Calendar feed</h2>
      <p className="dates">
        Subscribe in Google/Apple Calendar — read-only, shows todos
        assigned to you. Keep this URL secret.
      </p>
      <div className="add-row">
        <input readOnly value={feedUrl} onFocus={(e) => e.target.select()} />
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText(feedUrl)}
        >
          Copy
        </button>
        <button
          type="button"
          className="link-btn danger"
          onClick={() => {
            if (window.confirm('Old URL will stop working. Continue?'))
              regenFeed()
          }}
        >
          Regenerate
        </button>
      </div>
    </section>
  )
}
