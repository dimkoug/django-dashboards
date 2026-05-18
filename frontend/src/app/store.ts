import { configureStore } from '@reduxjs/toolkit'
import { api } from '../features/api/apiSlice'
import authReducer from '../features/auth/authSlice'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    [api.reducerPath]: api.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(api.middleware),
})

// Inferred types for the whole store — used by the typed hooks.
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
