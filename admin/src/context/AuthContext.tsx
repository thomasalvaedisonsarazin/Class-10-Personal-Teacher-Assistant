import { useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { AuthContext, type AuthContextValue, type AuthStatus } from '@/context/authContextValue';
import { onLogout } from '@/lib/authEvents';
import { tokenStorage } from '@/lib/tokenStorage';
import { getApiErrorMessage } from '@/services/api';
import { fetchCurrentUser, logout as logoutRequest } from '@/services/auth';
import type { AuthTokens, User } from '@/types/api';

const NOT_ADMIN_MESSAGE = 'This account does not have admin access.';
const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please sign in again.';

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>(() =>
    tokenStorage.getAccessToken() ? 'loading' : 'unauthenticated',
  );
  const [message, setMessage] = useState<string | null>(null);

  const endSession = useCallback(
    (reason: string | null) => {
      tokenStorage.clear();
      queryClient.clear();
      setUser(null);
      setStatus('unauthenticated');
      setMessage(reason);
    },
    [queryClient],
  );

  /** Accepts the /auth/me result; anyone who is not an admin is signed out. */
  const applyUser = useCallback(
    (me: User): User | null => {
      if (me.role !== 'admin') {
        endSession(NOT_ADMIN_MESSAGE);
        return null;
      }
      setUser(me);
      setStatus('authenticated');
      setMessage(null);
      return me;
    },
    [endSession],
  );

  const handleUserError = useCallback(
    (err: unknown): null => {
      const httpStatus = isAxiosError(err) ? err.response?.status : undefined;
      if (httpStatus === 401 || httpStatus === 403) {
        endSession(httpStatus === 403 ? NOT_ADMIN_MESSAGE : SESSION_EXPIRED_MESSAGE);
      } else {
        // Network or server error: keep the tokens so a reload can recover.
        setUser(null);
        setStatus('unauthenticated');
        setMessage(getApiErrorMessage(err));
      }
      return null;
    },
    [endSession],
  );

  const refreshUser = useCallback(async (): Promise<User | null> => {
    if (!tokenStorage.getAccessToken()) {
      endSession(null);
      return null;
    }
    try {
      return applyUser(await fetchCurrentUser());
    } catch (err: unknown) {
      return handleUserError(err);
    }
  }, [applyUser, endSession, handleUserError]);

  const signIn = useCallback(
    async (tokens: AuthTokens): Promise<User | null> => {
      tokenStorage.setTokens(tokens);
      setStatus('loading');
      return refreshUser();
    },
    [refreshUser],
  );

  const signOut = useCallback(async (): Promise<void> => {
    const refreshToken = tokenStorage.getRefreshToken();
    if (refreshToken) {
      try {
        await logoutRequest(refreshToken);
      } catch {
        // Best effort: the local session is cleared regardless.
      }
    }
    endSession(null);
  }, [endSession]);

  const clearMessage = useCallback(() => setMessage(null), []);

  // Restore the session on first load.
  useEffect(() => {
    if (!tokenStorage.getAccessToken()) return undefined;
    let active = true;
    fetchCurrentUser().then(
      (me) => {
        if (active) applyUser(me);
      },
      (err: unknown) => {
        if (active) handleUserError(err);
      },
    );
    return () => {
      active = false;
    };
  }, [applyUser, handleUserError]);

  // The API client emits this when a refresh fails.
  useEffect(() => onLogout(() => endSession(SESSION_EXPIRED_MESSAGE)), [endSession]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, message, signIn, signOut, refreshUser, clearMessage }),
    [user, status, message, signIn, signOut, refreshUser, clearMessage],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
