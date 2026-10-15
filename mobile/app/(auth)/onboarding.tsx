import { Redirect } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { AppText, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { spacing } from '@/theme';

/** Placeholder — Phase 2 adds BoardPicker + MediumPicker. */
export default function OnboardingScreen() {
  const { status } = useAuth();

  if (status === 'signedOut') {
    return <Redirect href="/login" />;
  }

  return (
    <Screen testID="onboarding-screen">
      <View style={styles.content}>
        <AppText variant="display" center>
          Set up your studies
        </AppText>
        <AppText tone="secondary" center>
          Choose your board and medium
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
