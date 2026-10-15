import type { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/hooks/useAuth';

export interface ProtectedRouteProps {
  /** Rendered when allowed; defaults to the nested route <Outlet />. */
  children?: ReactNode;
}

export interface LoginRedirectState {
  from?: string;
}

/** Only signed-in admins get through; everyone else is sent to /login. */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <LoadingState label="Checking your session..." fullPage />;
  }

  if (status !== 'authenticated' || !user || user.role !== 'admin') {
    const state: LoginRedirectState = { from: `${location.pathname}${location.search}` };
    return <Navigate to="/login" replace state={state} />;
  }

  return children ? <>{children}</> : <Outlet />;
}
