import { createContext } from 'react';

import type { AuthTokens, User } from '@/types/api';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  /** Why the admin was signed out (expired session, not an admin, ...). */
  message: string | null;
  signIn: (tokens: AuthTokens) => Promise<User | null>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  clearMessage: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
