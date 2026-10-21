import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AppState } from 'react-native';

import { authEvents } from '@/lib/authEvents';
import { SESSION_ACTIVE, getApiErrorCode } from '@/services/api';
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
  /** The account is open on another device; the app shows a "close it there" screen. */
  sessionBusy: boolean;
  /** Try again after closing the app on the other device. */
  retrySession: () => Promise<void>;
}

/** The app tells the server it is still open this often (the server frees it after ~2.5 min). */
const SESSION_PING_MS = 60_000;

export const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

function statusForUser(user: User): AuthStatus {
  // Partners (schools / teachers) only use their dashboard: no study setup.
  if (user.role === 'partner') return 'signedIn';
  if (user.medium === null) return 'needsOnboarding';
  if (user.role === 'student' && user.needsSubjects === true) return 'needsOnboarding';
  // Parents follow their children's boards; students need their own.
  if (user.role === 'student' && user.boardId === null) return 'needsOnboarding';
  return 'signedIn';
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [sessionBusy, setSessionBusy] = useState(false);
  const mounted = useRef(true);

  const resetSession = useCallback(() => {
    if (!mounted.current) {
      return;
    }
    setUser(null);
    setStatus('signedOut');
    setSessionBusy(false);
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    try {
      const me = await authService.getMe();
      if (mounted.current) {
        setUser(me);
        setStatus(statusForUser(me));
      }
      return me;
    } catch (err) {
      // In use on another device: the busy screen shows; keep everything as it is.
      if (getApiErrorCode(err) === SESSION_ACTIVE) {
        return null;
      }
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

  const retrySession = useCallback(async (): Promise<void> => {
    try {
      await authService.pingSession();
      setSessionBusy(false);
      await refreshUser();
    } catch {
      // Still busy (the interceptor flagged it again) or offline: stay on the busy screen.
    }
  }, [refreshUser]);

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
    const unsubscribeBusy = authEvents.onSessionBusy(() => {
      if (mounted.current) setSessionBusy(true);
    });

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
      unsubscribeBusy();
    };
  }, [refreshUser, resetSession]);

  // Once signed in (any role), make sure this phone can receive reminders.
  const userId = user?.id ?? null;
  useEffect(() => {
    if (status === 'signedIn' && userId !== null) {
      void registerForPushNotifications();
    }
  }, [status, userId]);

  // One device at a time (students): keep this phone's session alive while the app is open,
  // and free the account as soon as the app goes to the background.
  const isStudent = user?.role === 'student';
  useEffect(() => {
    if (!isStudent || status === 'signedOut' || status === 'loading') {
      return undefined;
    }
    let timer: ReturnType<typeof setInterval> | null = null;
    const ping = (): void => {
      void authService.pingSession().catch(() => undefined);
    };
    const start = (): void => {
      if (timer === null) timer = setInterval(ping, SESSION_PING_MS);
    };
    const stop = (): void => {
      if (timer !== null) clearInterval(timer);
      timer = null;
    };
    start();
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') {
        ping();
        start();
      } else if (next === 'background') {
        stop();
        void authService.releaseSession().catch(() => undefined);
      }
    });
    return () => {
      stop();
      sub.remove();
    };
  }, [isStudent, status]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, signIn, signOut, refreshUser, sessionBusy, retrySession }),
    [user, status, signIn, signOut, refreshUser, sessionBusy, retrySession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
