import { ChakraProvider } from '@chakra-ui/react';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';

import { AuthContext, type AuthContextValue } from '@/context/authContextValue';
import { system } from '@/theme';

export interface RenderOptions {
  route?: string;
  auth?: Partial<AuthContextValue>;
}

const noopAsync = async (): Promise<null> => null;

export function createAuthValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: null,
    status: 'unauthenticated',
    message: null,
    signIn: noopAsync,
    signOut: async () => undefined,
    refreshUser: noopAsync,
    clearMessage: () => undefined,
    ...overrides,
  };
}

/** Renders with Chakra, a memory router and a controllable auth context. */
export function renderWithProviders(ui: ReactElement, options: RenderOptions = {}): RenderResult {
  const { route = '/', auth } = options;
  return render(
    <ChakraProvider value={system}>
      <AuthContext.Provider value={createAuthValue(auth)}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </ChakraProvider>,
  );
}
