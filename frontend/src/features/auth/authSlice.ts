import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'

interface AuthState {
  access: string | null
  refresh: string | null
  username: string | null
}

const STORAGE_KEY = 'dashboard.auth'

function load(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as AuthState
  } catch {
    /* ignore corrupt storage */
  }
  return { access: null, refresh: null, username: null }
}

function persist(state: AuthState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* storage unavailable — stay in-memory */
  }
}

const authSlice = createSlice({
  name: 'auth',
  initialState: load(),
  reducers: {
    // Full login result (access + refresh + who).
    setCredentials: (
      state,
      action: PayloadAction<{ access: string; refresh: string; username: string }>,
    ) => {
      state.access = action.payload.access
      state.refresh = action.payload.refresh
      state.username = action.payload.username
      persist(state)
    },
    // Just a refreshed access token.
    setAccess: (state, action: PayloadAction<string>) => {
      state.access = action.payload
      persist(state)
    },
    logout: (state) => {
      state.access = null
      state.refresh = null
      state.username = null
      persist(state)
    },
  },
})

export const { setCredentials, setAccess, logout } = authSlice.actions
export default authSlice.reducer
