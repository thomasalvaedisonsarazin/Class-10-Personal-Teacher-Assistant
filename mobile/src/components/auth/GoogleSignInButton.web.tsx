import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { useEffect } from 'react';

import { PrimaryButton } from '@/components/ui';
import { env } from '@/lib/env';

void WebBrowser.maybeCompleteAuthSession();

export interface GoogleSignInButtonProps {
  /** Called with the Google ID token; the caller exchanges it with the API. */
  onIdToken: (idToken: string) => void;
  onError: (message: string) => void;
  loading?: boolean;
}

/** True when the OAuth client IDs needed for Google Sign-In are configured. */
export const isGoogleSignInConfigured = Boolean(env.googleWebClientId);

/**
 * Web preview: Google Sign-In via expo-auth-session (ID-token flow). Render only when
 * `isGoogleSignInConfigured` is true — the hook throws without client IDs.
 */
export function GoogleSignInButton({ onIdToken, onError, loading = false }: GoogleSignInButtonProps) {
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    webClientId: env.googleWebClientId,
    androidClientId: env.googleAndroidClientId || undefined,
  });

  useEffect(() => {
    if (!response) {
      return;
    }
    if (response.type === 'success') {
      const idToken = response.params.id_token;
      if (idToken) {
        onIdToken(idToken);
      } else {
        onError('Google did not return a sign-in token. Please try again.');
      }
    } else if (response.type === 'error') {
      onError('Google sign-in failed. Please try again.');
    }
  }, [response, onIdToken, onError]);

  const handlePress = (): void => {
    promptAsync().catch(() => onError('Could not open Google sign-in. Please try again.'));
  };

  return (
    <PrimaryButton
      label="Continue with Google"
      icon="google"
      onPress={handlePress}
      disabled={!request}
      loading={loading}
      testID="google-sign-in"
    />
  );
}
