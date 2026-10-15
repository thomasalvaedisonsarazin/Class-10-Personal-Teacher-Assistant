import { Redirect, Stack } from 'expo-router';

import { LoadingView } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { palette } from '@/theme';

const screenOptions = {
  headerShown: false,
  animation: 'fade',
  contentStyle: { backgroundColor: palette.background },
} as const;

export default function AuthLayout() {
  const { status } = useAuth();

  if (status === 'loading') {
    return <LoadingView />;
  }
  if (status === 'signedIn') {
    return <Redirect href="/" />;
  }

  return (
    <Stack screenOptions={screenOptions}>
      <Stack.Screen name="login" />
      <Stack.Screen name="onboarding" />
    </Stack>
  );
}
