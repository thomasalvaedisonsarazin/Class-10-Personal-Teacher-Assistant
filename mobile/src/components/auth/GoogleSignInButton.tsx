import {
  GoogleSignin,
  isErrorWithCode,
  isSuccessResponse,
  statusCodes,
} from '@react-native-google-signin/google-signin';
import { useState } from 'react';

import { PrimaryButton } from '@/components/ui';
import { env } from '@/lib/env';

export interface GoogleSignInButtonProps {
  /** Called with the Google ID token; the caller exchanges it with the API. */
  onIdToken: (idToken: string) => void;
  onError: (message: string) => void;
  loading?: boolean;
}

/** True when the OAuth client IDs needed for Google Sign-In are configured. */
export const isGoogleSignInConfigured = Boolean(env.googleWebClientId);

if (isGoogleSignInConfigured) {
  // The ID token's audience is the Web client; Google matches this app to the
  // Android client by package name + signing SHA-1.
  GoogleSignin.configure({ webClientId: env.googleWebClientId });
}

/**
 * Phone: native Google Sign-In (Android account picker, no browser redirect).
 * The web preview uses GoogleSignInButton.web.tsx instead.
 */
export function GoogleSignInButton({ onIdToken, onError, loading = false }: GoogleSignInButtonProps) {
  const [busy, setBusy] = useState(false);

  const handlePress = async (): Promise<void> => {
    setBusy(true);
    try {
      await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
      // Always show the account picker so students on a shared phone can choose.
      await GoogleSignin.signOut();
      const response = await GoogleSignin.signIn();
      if (!isSuccessResponse(response)) {
        return; // the student closed the picker
      }
      if (response.data.idToken) {
        onIdToken(response.data.idToken);
      } else {
        onError('Google did not return a sign-in token. Please try again.');
      }
    } catch (err) {
      if (isErrorWithCode(err) && err.code === statusCodes.SIGN_IN_CANCELLED) {
        return;
      }
      if (isErrorWithCode(err) && err.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        onError('Google Play services is missing or out of date. Please use email sign-in.');
        return;
      }
      onError('Google sign-in failed. Please try again or use email sign-in.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <PrimaryButton
      label="Continue with Google"
      icon="google"
      onPress={() => void handlePress()}
      disabled={busy}
      loading={loading || busy}
      testID="google-sign-in"
    />
  );
}
