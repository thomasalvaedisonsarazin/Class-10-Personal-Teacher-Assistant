import { Redirect, Stack } from 'expo-router';

import { LoadingView } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { palette } from '@/theme';

const screenOptions = {
  headerShown: false,
  animation: 'fade',
  contentStyle: { backgroundColor: palette.background },
} as const;

export default function AppLayout() {
  const { status } = useAuth();

  if (status === 'loading') {
    return <LoadingView />;
  }
  if (status === 'signedOut') {
    return <Redirect href="/login" />;
  }
  if (status === 'needsOnboarding') {
    return <Redirect href="/onboarding" />;
  }

  return <Stack screenOptions={screenOptions} />;
}
