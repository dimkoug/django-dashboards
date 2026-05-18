import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type {
  BaseQueryFn,
  FetchArgs,
  FetchBaseQueryError,
} from '@reduxjs/toolkit/query'
import type { RootState } from '../../app/store'
import { logout, setAccess } from '../auth/authSlice'

// ---- Types (mirror the DRF serializers) ----
export interface Dashboard {
  id: number
  name: string
  is_owner: boolean
  users: number[]
  members: { id: number; username: string }[]
  created_at: string
  updated_at: string
}

export interface Column {
  id: number
  dashboard: number
  name: string
  created_at: string
  updated_at: string
}

export type Priority = 'low' | 'medium' | 'high'
export type Recurrence = 'none' | 'daily' | 'weekly' | 'monthly'

export interface Label {
  id: number
  dashboard: number
  name: string
  color: string
  created_at: string
  updated_at: string
}

export interface Todo {
  id: number
  column: number
  name: string
  description: string
  description_html: string
  priority: Priority
  users: number[]
  assignees: { id: number; username: string }[]
  labels: number[]
  blockers: number[]
  blockers_open: number
  position: number
  recurrence: Recurrence
  subtask_summary: { total: number; done: number }
  start_date: string
  end_date: string | null
  completed: boolean
  created_at: string
  updated_at: string
}

export interface User {
  id: number
  username: string
}

export interface Me {
  id: number
  username: string
  email: string
}

export interface Comment {
  id: number
  todo: number
  author_username: string
  body: string
  created_at: string
}

export interface SearchResults {
  todos: {
    id: number
    name: string
    column: number
    dashboard_id: number
    dashboard_name: string
  }[]
  comments: {
    id: number
    body: string
    author: string | null
    todo: number
    todo_name: string
    dashboard_id: number
    column: number
  }[]
}

export interface SavedView {
  id: number
  name: string
  params: Record<string, unknown>
  created_at: string
}

export interface Subtask {
  id: number
  todo: number
  text: string
  done: boolean
  position: number
  created_at: string
}

export interface Webhook {
  id: number
  dashboard: number
  url: string
  events: string[]
  active: boolean
  created_at: string
}

export interface AppNotification {
  id: number
  kind: string
  text: string
  link: string
  read: boolean
  created_at: string
}

export interface DashboardStats {
  total: number
  open: number
  completed: number
  overdue: number
  by_priority: { low: number; medium: number; high: number }
  by_column: { id: number; name: string; total: number; completed: number }[]
  by_assignee: { username: string; count: number }[]
}

export interface Activity {
  id: number
  dashboard: number
  actor_username: string | null
  verb: string
  message: string
  created_at: string
}

export interface Attachment {
  id: number
  todo: number
  file_url: string
  original_name: string
  uploaded_by_username: string | null
  size: number | null
  created_at: string
}

interface TokenPair {
  access: string
  refresh: string
}

// Same-origin: nginx proxies /api/ to Django (uvicorn).
const rawBaseQuery = fetchBaseQuery({
  baseUrl: '/api',
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.access
    if (token) headers.set('authorization', `Bearer ${token}`)
    return headers
  },
})

// On 401, try one refresh with the stored refresh token, then retry once.
const baseQueryWithReauth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extraOptions) => {
  let result = await rawBaseQuery(args, api, extraOptions)

  if (result.error && result.error.status === 401) {
    const refresh = (api.getState() as RootState).auth.refresh
    if (refresh) {
      const refreshResult = await rawBaseQuery(
        { url: '/auth/token/refresh/', method: 'POST', body: { refresh } },
        api,
        extraOptions,
      )
      const data = refreshResult.data as { access?: string } | undefined
      if (data?.access) {
        api.dispatch(setAccess(data.access))
        result = await rawBaseQuery(args, api, extraOptions)
      } else {
        api.dispatch(logout())
      }
    } else {
      api.dispatch(logout())
    }
  }
  return result
}

// DRF list endpoints are paginated ({count,next,previous,results}); the
// `assigned` action returns a plain array. Normalise both to T[].
type Paginated<T> = { results: T[] }
function unwrap<T>(r: Paginated<T> | T[]): T[] {
  return Array.isArray(r) ? r : r.results
}
// The SPA needs whole lists (board, client-side filtering); request a
// large page. API consumers still get real pagination + ?page=.
const ALL = '?page_size=1000'

export const api = createApi({
  reducerPath: 'api',
  baseQuery: baseQueryWithReauth,
  tagTypes: [
    'Dashboard', 'Column', 'Label', 'Todo', 'Comment', 'Activity', 'Me',
    'Attachment', 'SavedView', 'Subtask', 'CalendarFeed', 'Notification',
    'Webhook',
  ],
  endpoints: (builder) => ({
    // ---- Auth ----
    register: builder.mutation<
      { id: number; username: string; email: string },
      { username: string; email: string; password: string }
    >({
      query: (body) => ({ url: '/auth/register/', method: 'POST', body }),
    }),
    login: builder.mutation<TokenPair, { username: string; password: string }>({
      query: (body) => ({ url: '/auth/token/', method: 'POST', body }),
    }),

    // ---- Users: search-only lookup (no enumeration) ----
    searchUsers: builder.query<User[], string>({
      query: (term) => `/users/?search=${encodeURIComponent(term)}`,
      transformResponse: (r: Paginated<User> | User[]) => unwrap(r),
    }),

    // ---- Account ----
    getMe: builder.query<Me, void>({
      query: () => '/auth/me/',
      providesTags: [{ type: 'Me', id: 'SELF' }],
    }),
    updateMe: builder.mutation<Me, { email: string }>({
      query: (body) => ({ url: '/auth/me/', method: 'PATCH', body }),
      invalidatesTags: [{ type: 'Me', id: 'SELF' }],
    }),
    changePassword: builder.mutation<
      { status: string },
      { old_password: string; new_password: string }
    >({
      query: (body) => ({
        url: '/auth/change-password/',
        method: 'POST',
        body,
      }),
    }),
    logoutServer: builder.mutation<void, { refresh: string }>({
      query: (body) => ({ url: '/auth/logout/', method: 'POST', body }),
    }),
    createWsTicket: builder.mutation<{ ticket: string }, void>({
      query: () => ({ url: '/ws-ticket/', method: 'POST' }),
    }),
    getPreferences: builder.query<
      { email_on_assign: boolean; email_on_mention: boolean },
      void
    >({
      query: () => '/auth/preferences/',
      providesTags: [{ type: 'Me', id: 'PREFS' }],
    }),
    updatePreferences: builder.mutation<
      { email_on_assign: boolean; email_on_mention: boolean },
      { email_on_assign?: boolean; email_on_mention?: boolean }
    >({
      query: (body) => ({
        url: '/auth/preferences/',
        method: 'PATCH',
        body,
      }),
      invalidatesTags: [{ type: 'Me', id: 'PREFS' }],
    }),

    // ---- Dashboards ----
    getDashboards: builder.query<Dashboard[], void>({
      query: () => `/dashboards/${ALL}`,
      transformResponse: (r: Paginated<Dashboard> | Dashboard[]) => unwrap(r),
      providesTags: (result) =>
        result
          ? [
              ...result.map((d) => ({ type: 'Dashboard' as const, id: d.id })),
              { type: 'Dashboard' as const, id: 'LIST' },
            ]
          : [{ type: 'Dashboard' as const, id: 'LIST' }],
    }),
    addDashboard: builder.mutation<Dashboard, { name: string }>({
      query: (body) => ({ url: '/dashboards/', method: 'POST', body }),
      invalidatesTags: [{ type: 'Dashboard', id: 'LIST' }],
    }),
    updateDashboard: builder.mutation<
      Dashboard,
      { id: number; name?: string; users?: number[] }
    >({
      query: ({ id, ...body }) => ({
        url: `/dashboards/${id}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: 'Dashboard', id },
        { type: 'Dashboard', id: 'LIST' },
      ],
    }),
    deleteDashboard: builder.mutation<void, number>({
      query: (id) => ({ url: `/dashboards/${id}/`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'Dashboard', id: 'LIST' }],
    }),

    // ---- Columns ----
    getColumns: builder.query<Column[], void>({
      query: () => `/columns/${ALL}`,
      transformResponse: (r: Paginated<Column> | Column[]) => unwrap(r),
      providesTags: (result) =>
        result
          ? [
              ...result.map((c) => ({ type: 'Column' as const, id: c.id })),
              { type: 'Column' as const, id: 'LIST' },
            ]
          : [{ type: 'Column' as const, id: 'LIST' }],
    }),
    addColumn: builder.mutation<
      Column,
      { dashboard: number; name: string }
    >({
      query: (body) => ({ url: '/columns/', method: 'POST', body }),
      invalidatesTags: [{ type: 'Column', id: 'LIST' }],
    }),
    updateColumn: builder.mutation<Column, { id: number; name: string }>({
      query: ({ id, ...body }) => ({
        url: `/columns/${id}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [{ type: 'Column', id }],
    }),
    deleteColumn: builder.mutation<void, number>({
      query: (id) => ({ url: `/columns/${id}/`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'Column', id: 'LIST' }],
    }),

    // ---- Labels (dashboard-scoped) ----
    getLabels: builder.query<Label[], void>({
      query: () => `/labels/${ALL}`,
      transformResponse: (r: Paginated<Label> | Label[]) => unwrap(r),
      providesTags: [{ type: 'Label', id: 'LIST' }],
    }),
    addLabel: builder.mutation<
      Label,
      { dashboard: number; name: string; color: string }
    >({
      query: (body) => ({ url: '/labels/', method: 'POST', body }),
      invalidatesTags: [{ type: 'Label', id: 'LIST' }],
    }),
    updateLabel: builder.mutation<
      Label,
      { id: number; name?: string; color?: string }
    >({
      query: ({ id, ...body }) => ({
        url: `/labels/${id}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: [{ type: 'Label', id: 'LIST' }],
    }),
    deleteLabel: builder.mutation<void, number>({
      query: (id) => ({ url: `/labels/${id}/`, method: 'DELETE' }),
      invalidatesTags: [
        { type: 'Label', id: 'LIST' },
        { type: 'Todo', id: 'LIST' },
      ],
    }),

    // ---- Todos ----
    getTodos: builder.query<Todo[], void>({
      query: () => `/todos/${ALL}`,
      transformResponse: (r: Paginated<Todo> | Todo[]) => unwrap(r),
      providesTags: (result) =>
        result
          ? [
              ...result.map((t) => ({ type: 'Todo' as const, id: t.id })),
              { type: 'Todo' as const, id: 'LIST' },
            ]
          : [{ type: 'Todo' as const, id: 'LIST' }],
    }),
    // Todos the logged-in user is assigned to (any dashboard).
    getAssignedTodos: builder.query<Todo[], void>({
      query: () => '/todos/assigned/',
      transformResponse: (r: Paginated<Todo> | Todo[]) => unwrap(r),
      providesTags: [{ type: 'Todo', id: 'ASSIGNED' }],
    }),
    addTodo: builder.mutation<
      Todo,
      {
        column: number
        name: string
        description?: string
        priority?: Priority
        recurrence?: Recurrence
        users?: number[]
        labels?: number[]
        blockers?: number[]
        start_date?: string
        end_date?: string | null
        completed?: boolean
      }
    >({
      query: (body) => ({ url: '/todos/', method: 'POST', body }),
      invalidatesTags: [
        { type: 'Todo', id: 'LIST' },
        { type: 'Todo', id: 'ASSIGNED' },
        { type: 'Activity', id: 'LIST' },
      ],
    }),
    updateTodo: builder.mutation<
      Todo,
      {
        id: number
        // Changing `column` moves the todo to another column.
        column?: number
        name?: string
        description?: string
        priority?: Priority
        recurrence?: Recurrence
        users?: number[]
        labels?: number[]
        blockers?: number[]
        start_date?: string
        end_date?: string | null
        completed?: boolean
      }
    >({
      query: ({ id, ...body }) => ({
        url: `/todos/${id}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: 'Todo', id },
        { type: 'Todo', id: 'ASSIGNED' },
        { type: 'Activity', id: 'LIST' },
      ],
    }),
    deleteTodo: builder.mutation<void, number>({
      query: (id) => ({ url: `/todos/${id}/`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'Todo', id: 'LIST' }],
    }),
    bulkTodos: builder.mutation<
      { updated?: number; deleted?: number },
      {
        ids: number[]
        action: 'complete' | 'reopen' | 'move' | 'label_add' | 'delete'
        value?: number
      }
    >({
      query: (body) => ({ url: '/todos/bulk/', method: 'POST', body }),
      invalidatesTags: [
        { type: 'Todo', id: 'LIST' },
        { type: 'Todo', id: 'ASSIGNED' },
        { type: 'Activity', id: 'LIST' },
      ],
    }),
    reorderTodos: builder.mutation<
      { status: string },
      { column: number; order: number[] }
    >({
      query: (body) => ({ url: '/todos/reorder/', method: 'POST', body }),
      invalidatesTags: [{ type: 'Todo', id: 'LIST' }],
    }),

    // ---- Subtasks ----
    getSubtasks: builder.query<Subtask[], number>({
      query: (todoId) => `/subtasks/?todo=${todoId}&page_size=1000`,
      transformResponse: (r: Paginated<Subtask> | Subtask[]) => unwrap(r),
      providesTags: [{ type: 'Subtask', id: 'LIST' }],
    }),
    addSubtask: builder.mutation<
      Subtask,
      { todo: number; text: string }
    >({
      query: (body) => ({ url: '/subtasks/', method: 'POST', body }),
      invalidatesTags: [
        { type: 'Subtask', id: 'LIST' },
        { type: 'Todo', id: 'LIST' },
      ],
    }),
    updateSubtask: builder.mutation<
      Subtask,
      { id: number; text?: string; done?: boolean }
    >({
      query: ({ id, ...body }) => ({
        url: `/subtasks/${id}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: [
        { type: 'Subtask', id: 'LIST' },
        { type: 'Todo', id: 'LIST' },
      ],
    }),
    deleteSubtask: builder.mutation<void, number>({
      query: (id) => ({ url: `/subtasks/${id}/`, method: 'DELETE' }),
      invalidatesTags: [
        { type: 'Subtask', id: 'LIST' },
        { type: 'Todo', id: 'LIST' },
      ],
    }),

    // ---- Comments ----
    getComments: builder.query<Comment[], number>({
      query: (todoId) => `/comments/?todo=${todoId}&page_size=1000`,
      transformResponse: (r: Paginated<Comment> | Comment[]) => unwrap(r),
      providesTags: [{ type: 'Comment', id: 'LIST' }],
    }),
    addComment: builder.mutation<
      Comment,
      { todo: number; body: string }
    >({
      query: (body) => ({ url: '/comments/', method: 'POST', body }),
      invalidatesTags: [
        { type: 'Comment', id: 'LIST' },
        { type: 'Activity', id: 'LIST' },
      ],
    }),
    deleteComment: builder.mutation<void, number>({
      query: (id) => ({ url: `/comments/${id}/`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'Comment', id: 'LIST' }],
    }),

    // ---- Activity feed ----
    getActivity: builder.query<Activity[], number>({
      query: (dashboardId) =>
        `/activity/?dashboard=${dashboardId}&page_size=1000`,
      transformResponse: (r: Paginated<Activity> | Activity[]) => unwrap(r),
      providesTags: [{ type: 'Activity', id: 'LIST' }],
    }),

    // ---- Notification center ----
    getNotifications: builder.query<AppNotification[], void>({
      query: () => `/notifications/${ALL}`,
      transformResponse: (r: Paginated<AppNotification> | AppNotification[]) =>
        unwrap(r),
      providesTags: [{ type: 'Notification', id: 'LIST' }],
    }),
    getUnreadCount: builder.query<{ count: number }, void>({
      query: () => '/notifications/unread_count/',
      providesTags: [{ type: 'Notification', id: 'COUNT' }],
    }),
    markNotificationRead: builder.mutation<{ status: string }, number>({
      query: (id) => ({
        url: `/notifications/${id}/read/`,
        method: 'POST',
      }),
      invalidatesTags: [
        { type: 'Notification', id: 'LIST' },
        { type: 'Notification', id: 'COUNT' },
      ],
    }),
    markAllNotificationsRead: builder.mutation<{ status: string }, void>({
      query: () => ({ url: '/notifications/read_all/', method: 'POST' }),
      invalidatesTags: [
        { type: 'Notification', id: 'LIST' },
        { type: 'Notification', id: 'COUNT' },
      ],
    }),

    // ---- Webhooks (owner-managed) ----
    getWebhooks: builder.query<Webhook[], void>({
      query: () => `/webhooks/${ALL}`,
      transformResponse: (r: Paginated<Webhook> | Webhook[]) => unwrap(r),
      providesTags: [{ type: 'Webhook', id: 'LIST' }],
    }),
    addWebhook: builder.mutation<
      Webhook,
      { dashboard: number; url: string; events: string[]; active: boolean }
    >({
      query: (body) => ({ url: '/webhooks/', method: 'POST', body }),
      invalidatesTags: [{ type: 'Webhook', id: 'LIST' }],
    }),
    deleteWebhook: builder.mutation<void, number>({
      query: (id) => ({ url: `/webhooks/${id}/`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'Webhook', id: 'LIST' }],
    }),

    // ---- Calendar feed ----
    getCalendarFeed: builder.query<{ token: string; path: string }, void>({
      query: () => '/calendar/feed/',
      providesTags: [{ type: 'CalendarFeed', id: 'SELF' }],
    }),
    regenerateCalendarFeed: builder.mutation<
      { token: string; path: string },
      void
    >({
      query: () => ({ url: '/calendar/feed/', method: 'POST' }),
      invalidatesTags: [{ type: 'CalendarFeed', id: 'SELF' }],
    }),

    // ---- Global search ----
    globalSearch: builder.query<SearchResults, string>({
      query: (q) => `/search/?q=${encodeURIComponent(q)}`,
    }),

    // ---- Saved views (private filter presets) ----
    getSavedViews: builder.query<SavedView[], void>({
      query: () => `/saved-views/${ALL}`,
      transformResponse: (r: Paginated<SavedView> | SavedView[]) =>
        unwrap(r),
      providesTags: [{ type: 'SavedView', id: 'LIST' }],
    }),
    addSavedView: builder.mutation<
      SavedView,
      { name: string; params: Record<string, unknown> }
    >({
      query: (body) => ({ url: '/saved-views/', method: 'POST', body }),
      invalidatesTags: [{ type: 'SavedView', id: 'LIST' }],
    }),
    deleteSavedView: builder.mutation<void, number>({
      query: (id) => ({ url: `/saved-views/${id}/`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'SavedView', id: 'LIST' }],
    }),

    // ---- Analytics ----
    getDashboardStats: builder.query<DashboardStats, number>({
      query: (id) => `/dashboards/${id}/stats/`,
      providesTags: [{ type: 'Todo', id: 'LIST' }],
    }),

    // ---- Attachments ----
    getAttachments: builder.query<Attachment[], number>({
      query: (todoId) => `/attachments/?todo=${todoId}&page_size=1000`,
      transformResponse: (r: Paginated<Attachment> | Attachment[]) =>
        unwrap(r),
      providesTags: [{ type: 'Attachment', id: 'LIST' }],
    }),
    addAttachment: builder.mutation<
      Attachment,
      { todo: number; file: File }
    >({
      query: ({ todo, file }) => {
        const form = new FormData()
        form.append('todo', String(todo))
        form.append('file', file)
        return { url: '/attachments/', method: 'POST', body: form }
      },
      invalidatesTags: [
        { type: 'Attachment', id: 'LIST' },
        { type: 'Activity', id: 'LIST' },
      ],
    }),
    deleteAttachment: builder.mutation<void, number>({
      query: (id) => ({ url: `/attachments/${id}/`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'Attachment', id: 'LIST' }],
    }),
  }),
})

export const {
  useRegisterMutation,
  useLoginMutation,
  useSearchUsersQuery,
  useLazySearchUsersQuery,
  useGetMeQuery,
  useUpdateMeMutation,
  useChangePasswordMutation,
  useLogoutServerMutation,
  useCreateWsTicketMutation,
  useGetPreferencesQuery,
  useUpdatePreferencesMutation,
  useGetDashboardsQuery,
  useAddDashboardMutation,
  useUpdateDashboardMutation,
  useDeleteDashboardMutation,
  useGetColumnsQuery,
  useAddColumnMutation,
  useUpdateColumnMutation,
  useDeleteColumnMutation,
  useGetLabelsQuery,
  useAddLabelMutation,
  useUpdateLabelMutation,
  useDeleteLabelMutation,
  useGetTodosQuery,
  useGetAssignedTodosQuery,
  useAddTodoMutation,
  useUpdateTodoMutation,
  useDeleteTodoMutation,
  useReorderTodosMutation,
  useBulkTodosMutation,
  useGetCommentsQuery,
  useAddCommentMutation,
  useDeleteCommentMutation,
  useGetSubtasksQuery,
  useAddSubtaskMutation,
  useUpdateSubtaskMutation,
  useDeleteSubtaskMutation,
  useGetActivityQuery,
  useGlobalSearchQuery,
  useGetWebhooksQuery,
  useAddWebhookMutation,
  useDeleteWebhookMutation,
  useGetNotificationsQuery,
  useGetUnreadCountQuery,
  useMarkNotificationReadMutation,
  useMarkAllNotificationsReadMutation,
  useGetCalendarFeedQuery,
  useRegenerateCalendarFeedMutation,
  useGetSavedViewsQuery,
  useAddSavedViewMutation,
  useDeleteSavedViewMutation,
  useGetDashboardStatsQuery,
  useGetAttachmentsQuery,
  useAddAttachmentMutation,
  useDeleteAttachmentMutation,
} = api
