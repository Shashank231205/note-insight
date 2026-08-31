import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AuthProvider } from '@/contexts/AuthContext';
import { AppLayout } from '@/layouts/AppLayout';
import { HistoryPage } from '@/pages/HistoryPage';
import { LoginPage } from '@/pages/LoginPage';
import { NewNotePage } from '@/pages/NewNotePage';
import { NoteDetailPage } from '@/pages/NoteDetailPage';

export function App(): JSX.Element {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/notes/new" element={<NewNotePage />} />
              <Route path="/notes/:noteId" element={<NoteDetailPage />} />
              <Route path="/notes" element={<HistoryPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/notes/new" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
