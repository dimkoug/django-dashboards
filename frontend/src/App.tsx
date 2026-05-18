import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './components/RequireAuth'
import { Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { SignupPage } from './pages/SignupPage'
import { MyTodosPage } from './pages/MyTodosPage'
import { AccountPage } from './pages/AccountPage'
import { SearchPage } from './pages/SearchPage'
import { DashboardsPage } from './pages/DashboardsPage'
import { ColumnsPage } from './pages/ColumnsPage'
import { BoardPage } from './pages/BoardPage'
import { StatsPage } from './pages/StatsPage'
import { TodosPage } from './pages/TodosPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />

        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route path="/my-todos" element={<MyTodosPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/dashboards" element={<DashboardsPage />} />
            <Route
              path="/dashboards/:dashboardId"
              element={<ColumnsPage />}
            />
            <Route
              path="/dashboards/:dashboardId/board"
              element={<BoardPage />}
            />
            <Route
              path="/dashboards/:dashboardId/stats"
              element={<StatsPage />}
            />
            <Route
              path="/dashboards/:dashboardId/columns/:columnId"
              element={<TodosPage />}
            />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/my-todos" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
