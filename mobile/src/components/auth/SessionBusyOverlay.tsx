import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Icon } from 'react-native-paper';

import { AppText, PrimaryButton } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { palette, spacing } from '@/theme';

/**
 * Covers the app while this student's account is open on another device
 * (the API answers 409 `session_active`). Only one device may study at a time.
 */
export function SessionBusyOverlay() {
  const { sessionBusy, retrySession, signOut } = useAuth();
  const [retrying, setRetrying] = useState(false);

  if (!sessionBusy) {
    return null;
  }

  const retry = async (): Promise<void> => {
    setRetrying(true);
    try {
      await retrySession();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <View style={styles.overlay} testID="session-busy">
      <View style={styles.content}>
        <Icon source="cellphone-lock" size={56} color={palette.primary} />
        <AppText variant="title" center>
          An active session is open
        </AppText>
        <AppText tone="secondary" center>
          Your account is being used on another phone right now. Please close the app there, then
          open it here.
        </AppText>
        <AppText variant="caption" tone="secondary" center>
          If the other phone was switched off without closing the app, this frees itself in about 3
          minutes.
        </AppText>
        <PrimaryButton
          label="I closed it — open here"
          icon="refresh"
          onPress={() => void retry()}
          loading={retrying}
          testID="session-busy-retry"
        />
        <PrimaryButton label="Sign out" mode="text" onPress={() => void signOut()} disabled={retrying} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: palette.background,
    justifyContent: 'center',
    padding: spacing.xl,
  },
  content: {
    alignItems: 'center',
    gap: spacing.lg,
  },
});
