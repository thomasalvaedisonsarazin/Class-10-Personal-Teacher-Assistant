import { Box, Flex, Heading, Stack, Text } from '@chakra-ui/react';
import { Navigate, useLocation } from 'react-router-dom';

import type { LoginRedirectState } from '@/components/auth/ProtectedRoute';
import { Card } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { useAuth } from '@/hooks/useAuth';

function getRedirectTarget(state: unknown): string {
  const from = (state as LoginRedirectState | null)?.from;
  return typeof from === 'string' && from.startsWith('/admin') ? from : '/admin';
}

/** Placeholder: Google Sign-In (and the dev login) are wired up in Phase 2. */
export default function LoginPage() {
  const { status, message } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <LoadingState label="Checking your session..." fullPage />;
  }
  if (status === 'authenticated') {
    return <Navigate to={getRedirectTarget(location.state)} replace />;
  }

  return (
    <Flex minH="100vh" align="center" justify="center" bg="bg" px={4}>
      <Box w="full" maxW="sm">
        <PageWrapper>
          <Card>
            <Stack gap={3} textAlign="center">
              <Heading as="h1" size="lg" color="fg">
                Admin sign in
              </Heading>
              <Text color="fgMuted">
                Sign in with the Google account that has admin access to Teacher Assistant.
              </Text>
              {message && (
                <Text
                  role="alert"
                  bg="warning.subtle"
                  color="fg"
                  borderRadius="md"
                  px={3}
                  py={2}
                  fontSize="sm"
                >
                  {message}
                </Text>
              )}
              <Text fontSize="sm" color="fgMuted">
                Sign-in options will appear here.
              </Text>
            </Stack>
          </Card>
        </PageWrapper>
      </Box>
    </Flex>
  );
}
