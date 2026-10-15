import { ChakraProvider } from '@chakra-ui/react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

import { AuthProvider } from '@/context/AuthContext';
import { env } from '@/lib/env';
import { createQueryClient } from '@/lib/queryClient';
import { system } from '@/theme';

interface AppProvidersProps {
  children: ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  const [queryClient] = useState(createQueryClient);

  const content = (
    <ChakraProvider value={system}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    </ChakraProvider>
  );

  // The Google script only loads when a client id is configured.
  return env.googleClientId ? (
    <GoogleOAuthProvider clientId={env.googleClientId}>{content}</GoogleOAuthProvider>
  ) : (
    content
  );
}
