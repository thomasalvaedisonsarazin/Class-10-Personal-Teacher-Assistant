import { Redirect } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { AppText, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { spacing } from '@/theme';

/** Placeholder — Phase 2 adds GoogleSignInButton + DevLoginButton (dev builds only). */
export default function LoginScreen() {
  const { status } = useAuth();

  if (status === 'needsOnboarding') {
    return <Redirect href="/onboarding" />;
  }

  return (
    <Screen testID="login-screen">
      <View style={styles.content}>
        <AppText variant="display" center>
          Personal Teacher Assistant
        </AppText>
        <AppText tone="secondary" center>
          Sign in to continue
        </AppText>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
    justifyContent: 'center',
    gap: spacing.md,
  },
});
