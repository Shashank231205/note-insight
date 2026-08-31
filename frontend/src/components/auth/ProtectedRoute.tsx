import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { LoadingState } from '@/components/common/Feedback';
import { useAuth } from '@/hooks/useAuth';

/**
 * Gate for every authenticated route.
 *
 * Waits for Firebase to restore any persisted session before deciding. Without
 * that wait, a signed-in user refreshing the page would be bounced to login
 * for the moment before the session resolves.
 */
export function ProtectedRoute(): JSX.Element {
  const { user, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return <LoadingState message="Restoring your session…" />;
  }

  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
