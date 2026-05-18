import { useState } from 'react'
import AsyncSelect from 'react-select/async'
import type { MultiValue, StylesConfig } from 'react-select'
import { useLazySearchUsersQuery } from '../features/api/apiSlice'

type Opt = { value: number; label: string }

const styles: StylesConfig<Opt, true> = {
  control: (b) => ({
    ...b,
    background: '#1e293b',
    borderColor: '#334155',
    minWidth: 220,
  }),
  menu: (b) => ({ ...b, background: '#1e293b' }),
  option: (b, s) => ({
    ...b,
    background: s.isFocused ? '#334155' : '#1e293b',
    color: '#e2e8f0',
  }),
  multiValue: (b) => ({ ...b, background: '#4f46e5' }),
  multiValueLabel: (b) => ({ ...b, color: '#fff' }),
  multiValueRemove: (b) => ({ ...b, color: '#e2e8f0' }),
  input: (b) => ({ ...b, color: '#e2e8f0' }),
  placeholder: (b) => ({ ...b, color: '#64748b' }),
}

/**
 * Multi-user picker backed by the search-only /api/users endpoint
 * (no full-list enumeration). Seeded with already-selected users so
 * their names render without a global user list.
 */
export function AsyncUserSelect({
  initial,
  onChange,
  placeholder = 'Search users…',
}: {
  initial: { id: number; username: string }[]
  onChange: (ids: number[]) => void
  placeholder?: string
}) {
  const [selected, setSelected] = useState<Opt[]>(
    initial.map((u) => ({ value: u.id, label: u.username })),
  )
  const [trigger] = useLazySearchUsersQuery()

  const loadOptions = (input: string): Promise<Opt[]> => {
    if (input.trim().length < 2) return Promise.resolve([])
    return trigger(input.trim())
      .unwrap()
      .then((users) =>
        users.map((u) => ({ value: u.id, label: u.username })),
      )
      .catch(() => [])
  }

  return (
    <AsyncSelect<Opt, true>
      isMulti
      cacheOptions
      defaultOptions={false}
      value={selected}
      loadOptions={loadOptions}
      onChange={(v: MultiValue<Opt>) => {
        const next = [...v]
        setSelected(next)
        onChange(next.map((o) => o.value))
      }}
      styles={styles}
      placeholder={placeholder}
      noOptionsMessage={({ inputValue }) =>
        inputValue.length < 2 ? 'Type 2+ characters' : 'No users'
      }
    />
  )
}
