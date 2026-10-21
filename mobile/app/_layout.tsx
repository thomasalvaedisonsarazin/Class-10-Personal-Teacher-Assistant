import { QueryClientProvider } from '@tanstack/react-query';
import { useFonts } from 'expo-font';
import * as Notifications from 'expo-notifications';
import { Stack, useRouter } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from '@/context/AuthContext';
import { useAuth } from '@/hooks/useAuth';
import { queryClient } from '@/lib/queryClient';
import { targetFromData } from '@/services/pushService';
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

/** Opens the topic (student) or child report (parent) a notification points to. */
function NotificationRouter() {
  const router = useRouter();
  useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener((response) => {
      const target = targetFromData(response.notification.request.content.data);
      if (!target) return;
      if (target.screen === 'topic') {
        router.push({ pathname: '/topic/[id]', params: { id: String(target.id) } });
      } else if (target.screen === 'partner') {
        router.push('/partner');
      } else {
        router.push({ pathname: '/parent/[studentId]', params: { studentId: String(target.id) } });
      }
    });
    return () => sub.remove();
  }, [router]);
  return null;
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
            <NotificationRouter />
          </ThemedApp>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
