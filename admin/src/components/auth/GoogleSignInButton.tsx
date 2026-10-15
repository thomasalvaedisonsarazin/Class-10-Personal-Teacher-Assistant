import { Box, Text } from '@chakra-ui/react';
import { useEffect, useRef, useState } from 'react';

const GSI_SCRIPT_URL = 'https://accounts.google.com/gsi/client';
const BUTTON_WIDTH = 280;

let scriptPromise: Promise<void> | null = null;

/** Loads the Google Identity Services script once per page. */
function loadGoogleScript(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise<void>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = GSI_SCRIPT_URL;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => {
        scriptPromise = null;
        reject(new Error('Could not load Google Sign-In'));
      };
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

export interface GoogleSignInButtonProps {
  clientId: string;
  /** Receives the Google ID token to exchange with the API. */
  onCredential: (idToken: string) => void;
}

/** Renders Google's own "Sign in with Google" button (Google Identity Services). */
export function GoogleSignInButton({ clientId, onCredential }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const callbackRef = useRef(onCredential);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    callbackRef.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    let active = true;
    loadGoogleScript().then(
      () => {
        const googleId = window.google?.accounts.id;
        if (!active || !googleId || !containerRef.current) return;
        googleId.initialize({
          client_id: clientId,
          callback: (response) => callbackRef.current(response.credential),
          cancel_on_tap_outside: true,
        });
        googleId.renderButton(containerRef.current, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'rectangular',
          width: BUTTON_WIDTH,
        });
      },
      (err: unknown) => {
        if (active) setLoadError(err instanceof Error ? err.message : 'Could not load Google Sign-In');
      },
    );
    return () => {
      active = false;
    };
  }, [clientId]);

  if (loadError) {
    return (
      <Text fontSize="sm" color="danger">
        {loadError}. Check your internet connection and reload.
      </Text>
    );
  }
  return <Box ref={containerRef} display="flex" justifyContent="center" minH="44px" />;
}
