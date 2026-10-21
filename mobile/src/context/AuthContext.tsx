import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { authEvents } from '@/lib/authEvents';
import { authService } from '@/services/authService';
import { registerForPushNotifications, unregisterPushNotifications } from '@/services/pushService';
import { tokenStorage } from '@/services/tokenStorage';
import type { AuthTokens, User } from '@/types/api';

export type AuthStatus = 'loading' | 'signedOut' | 'needsOnboarding' | 'signedIn';

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  signIn: (tokens: AuthTokens) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

function statusForUser(user: User): AuthStatus {
  // Partners (schools / teachers) only use their dashboard: no study setup.
  if (user.role === 'partner') return 'signedIn';
  if (user.medium === null) return 'needsOnboarding';
  // Parents follow their children's boards; students need their own.
  if (user.role === 'student' && user.boardId === null) return 'needsOnboarding';
  return 'signedIn';
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const mounted = useRef(true);

  const resetSession = useCallback(() => {
    if (!mounted.current) {
      return;
    }
    setUser(null);
    setStatus('signedOut');
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    try {
      const me = await authService.getMe();
      if (mounted.current) {
        setUser(me);
        setStatus(statusForUser(me));
      }
      return me;
    } catch {
      // A 401 that could not be refreshed already cleared tokens and emitted logout.
      const tokens = await tokenStorage.getTokens();
      if (!tokens) {
        resetSession();
      } else if (mounted.current) {
        // Network/server error with valid tokens: keep the session, stay on current status.
        setStatus((prev) => (prev === 'loading' ? 'signedOut' : prev));
      }
      return null;
    }
  }, [resetSession]);

  const signIn = useCallback(
    async (tokens: AuthTokens): Promise<void> => {
      await tokenStorage.setTokens(tokens);
      await refreshUser();
    },
    [refreshUser],
  );

  const signOut = useCallback(async (): Promise<void> => {
    try {
      await unregisterPushNotifications();
      await authService.logout();
    } catch {
      // Ignore: server revoke is best-effort, local sign-out must always succeed.
    } finally {
      await tokenStorage.clear();
      resetSession();
    }
  }, [resetSession]);

  useEffect(() => {
    mounted.current = true;
    const unsubscribe = authEvents.onLogout(resetSession);

    const bootstrap = async (): Promise<void> => {
      try {
        const tokens = await tokenStorage.getTokens();
        if (!tokens) {
          resetSession();
          return;
        }
        await refreshUser();
      } catch {
        resetSession();
      }
    };
    void bootstrap();

    return () => {
      mounted.current = false;
      unsubscribe();
    };
  }, [refreshUser, resetSession]);

  // Once signed in (any role), make sure this phone can receive reminders.
  const userId = user?.id ?? null;
  useEffect(() => {
    if (status === 'signedIn' && userId !== null) {
      void registerForPushNotifications();
    }
  }, [status, userId]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, signIn, signOut, refreshUser }),
    [user, status, signIn, signOut, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
