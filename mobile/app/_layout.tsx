import { QueryClientProvider } from '@tanstack/react-query';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from '@/context/AuthContext';
import { useAuth } from '@/hooks/useAuth';
import { queryClient } from '@/lib/queryClient';
import { createAppTheme, fontAssets, palette } from '@/theme';

void SplashScreen.preventAutoHideAsync().catch(() => undefined);

interface ThemedAppProps {
  children: ReactNode;
}

/** Paper theme follows the student's medium so Tamil text uses Noto Sans Tamil. */
function ThemedApp({ children }: ThemedAppProps) {
  const { user } = useAuth();
  const medium = user?.medium ?? 'en';
  const theme = useMemo(() => createAppTheme(medium), [medium]);
  return <PaperProvider theme={theme}>{children}</PaperProvider>;
}

const screenOptions = {
  headerShown: false,
  animation: 'fade',
  contentStyle: { backgroundColor: palette.background },
} as const;

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(fontAssets);
  const ready = fontsLoaded || fontError !== null;

  useEffect(() => {
    if (ready) {
      void SplashScreen.hideAsync().catch(() => undefined);
    }
  }, [ready]);

  if (!ready) {
    return null;
  }

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ThemedApp>
            <StatusBar style="dark" />
            <Stack screenOptions={screenOptions} />
          </ThemedApp>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
