import { Box, Flex, Heading, Stack, Text } from '@chakra-ui/react';
import { useCallback, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { DevLoginForm } from '@/components/auth/DevLoginForm';
import { GoogleSignInButton } from '@/components/auth/GoogleSignInButton';
import type { LoginRedirectState } from '@/components/auth/ProtectedRoute';
import { Card } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { useAuth } from '@/hooks/useAuth';
import { env } from '@/lib/env';
import { getApiErrorMessage } from '@/services/api';
import { devLogin, loginWithGoogle } from '@/services/auth';
import type { AuthTokens } from '@/types/api';

function getRedirectTarget(state: unknown): string {
  const from = (state as LoginRedirectState | null)?.from;
  return typeof from === 'string' && from.startsWith('/admin') ? from : '/admin';
}

const showDevLogin = import.meta.env.DEV && env.enableDevLogin;

export default function LoginPage() {
  const { status, message, signIn, clearMessage } = useAuth();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const runSignIn = useCallback(
    async (getTokens: () => Promise<AuthTokens>): Promise<void> => {
      setError(null);
      clearMessage();
      setSubmitting(true);
      try {
        await signIn(await getTokens());
      } catch (err: unknown) {
        setError(getApiErrorMessage(err));
      } finally {
        setSubmitting(false);
      }
    },
    [signIn, clearMessage],
  );

  const handleGoogleCredential = useCallback(
    (idToken: string) => void runSignIn(() => loginWithGoogle(idToken)),
    [runSignIn],
  );

  if (status === 'loading') {
    return <LoadingState label="Checking your session..." fullPage />;
  }
  if (status === 'authenticated') {
    return <Navigate to={getRedirectTarget(location.state)} replace />;
  }

  const alertText = error ?? message;

  return (
    <Flex minH="100vh" align="center" justify="center" bg="bg" px={4}>
      <Box w="full" maxW="sm">
        <PageWrapper>
          <Card>
            <Stack gap={4} textAlign="center">
              <Heading as="h1" size="lg" color="fg">
                Admin sign in
              </Heading>
              <Text color="fgMuted">
                Sign in with the Google account that has admin access to Teacher Assistant.
              </Text>
              {alertText && (
                <Text
                  role="alert"
                  bg="warning.subtle"
                  color="fg"
                  borderRadius="md"
                  px={3}
                  py={2}
                  fontSize="sm"
                >
                  {alertText}
                </Text>
              )}
              {env.googleClientId ? (
                <GoogleSignInButton
                  clientId={env.googleClientId}
                  onCredential={handleGoogleCredential}
                />
              ) : (
                <Text fontSize="sm" color="fgMuted">
                  Google sign-in will appear here once it is set up.
                </Text>
              )}
              {showDevLogin && (
                <DevLoginForm
                  loading={submitting}
                  onSubmit={(email) => void runSignIn(() => devLogin(email))}
                />
              )}
            </Stack>
          </Card>
        </PageWrapper>
      </Box>
    </Flex>
  );
}
