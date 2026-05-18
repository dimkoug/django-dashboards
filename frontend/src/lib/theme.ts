import type { ThemePref } from '../features/api/apiSlice'

// Keep this key in sync with the no-flash inline script in index.html.
export const THEME_KEY = 'dashboard.theme'

export const THEME_ORDER: ThemePref[] = ['system', 'light', 'dark']

const lightMql = () =>
  window.matchMedia('(prefers-color-scheme: light)')

/** The concrete scheme a preference resolves to right now. */
export function resolveTheme(pref: ThemePref): 'light' | 'dark' {
  if (pref === 'light' || pref === 'dark') return pref
  return lightMql().matches ? 'light' : 'dark'
}

/** Last preference the user chose (defaults to 'system'). */
export function getStoredPref(): ThemePref {
  try {
    const v = localStorage.getItem(THEME_KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    /* storage unavailable */
  }
  return 'system'
}

/**
 * Apply a preference: set <html data-theme>, persist the raw choice,
 * and return the resolved scheme so callers can sync dependent UI.
 */
export function applyTheme(pref: ThemePref): 'light' | 'dark' {
  const resolved = resolveTheme(pref)
  document.documentElement.dataset.theme = resolved
  try {
    localStorage.setItem(THEME_KEY, pref)
  } catch {
    /* storage unavailable — still applied for this session */
  }
  return resolved
}

/** Subscribe to OS scheme changes; only relevant while pref is 'system'. */
export function onSystemThemeChange(cb: () => void): () => void {
  const m = lightMql()
  m.addEventListener('change', cb)
  return () => m.removeEventListener('change', cb)
}
