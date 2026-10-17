import { Redirect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { HelperText } from 'react-native-paper';

import { DevLoginButtons } from '@/components/auth/DevLoginButtons';
import { EmailSignIn } from '@/components/auth/EmailSignIn';
import { GoogleSignInButton, isGoogleSignInConfigured } from '@/components/auth/GoogleSignInButton';
import { AppText, PrimaryButton, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { env } from '@/lib/env';
import { getApiErrorMessage } from '@/services/api';
import { authService } from '@/services/authService';
import { spacing } from '@/theme';
import type { AuthTokens } from '@/types/api';

export default function LoginScreen() {
  const { status, signIn } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [devLoadingEmail, setDevLoadingEmail] = useState<string | null>(null);
  const [useEmail, setUseEmail] = useState(false);

  const handleEmailSignedIn = useCallback((tokens: AuthTokens): Promise<void> => signIn(tokens), [signIn]);

  const handleGoogleToken = useCallback(
    async (idToken: string): Promise<void> => {
      setError(null);
      setGoogleLoading(true);
      try {
        await signIn(await authService.loginWithGoogle(idToken));
      } catch (err) {
        setError(getApiErrorMessage(err));
      } finally {
        setGoogleLoading(false);
      }
    },
    [signIn],
  );

  const handleDevLogin = useCallback(
    async (email: string): Promise<void> => {
      setError(null);
      setDevLoadingEmail(email);
      try {
        await signIn(await authService.devLogin(email));
      } catch (err) {
        setError(getApiErrorMessage(err));
      } finally {
        setDevLoadingEmail(null);
      }
    },
    [signIn],
  );

  if (status === 'needsOnboarding') {
    return <Redirect href="/onboarding" />;
  }

  return (
    <Screen scroll testID="login-screen">
      <View style={styles.hero}>
        <AppText variant="display" center>
          Personal Teacher Assistant
        </AppText>
        <AppText tone="secondary" center>
          Learn one topic at a time. Ask again whenever it is not clear.
        </AppText>
      </View>

      <View style={styles.actions}>
        {useEmail ? (
          <EmailSignIn
            onSignedIn={handleEmailSignedIn}
            onError={setError}
            onCancel={() => {
              setError(null);
              setUseEmail(false);
            }}
          />
        ) : null}

        {!useEmail && isGoogleSignInConfigured ? (
          <GoogleSignInButton
            onIdToken={(token) => void handleGoogleToken(token)}
            onError={setError}
            loading={googleLoading}
          />
        ) : null}

        {useEmail ? null : (
          <PrimaryButton
            label="Continue with email"
            icon="email-outline"
            mode="outlined"
            onPress={() => {
              setError(null);
              setUseEmail(true);
            }}
            testID="continue-with-email"
          />
        )}

        {env.enableDevLogin && !useEmail ? (
          <DevLoginButtons onLogin={(email) => void handleDevLogin(email)} loadingEmail={devLoadingEmail} />
        ) : null}

        <HelperText type="error" visible={error !== null} style={styles.error} testID="login-error">
          {error ?? ''}
        </HelperText>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: {
    flex: 1,
    justifyContent: 'center',
    gap: spacing.md,
  },
  actions: {
    gap: spacing.md,
    paddingBottom: spacing.xl,
  },
  error: {
    textAlign: 'center',
  },
});
