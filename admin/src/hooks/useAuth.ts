import { useContext } from 'react';

import { AuthContext, type AuthContextValue } from '@/context/authContextValue';

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used inside an AuthProvider');
  }
  return context;
}
