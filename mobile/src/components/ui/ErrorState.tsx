import { StyleSheet, View } from 'react-native';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { palette, spacing } from '@/theme';

import { AppText } from './AppText';
import { PrimaryButton } from './PrimaryButton';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
  retrying?: boolean;
  testID?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'Please check your connection and try again.',
  onRetry,
  retryLabel = 'Try again',
  retrying = false,
  testID,
}: ErrorStateProps) {
  return (
    <View style={styles.container} accessibilityRole="alert" testID={testID}>
      <MaterialCommunityIcons name="cloud-alert-outline" size={48} color={palette.warning} />
      <AppText variant="subtitle" center style={styles.title}>
        {title}
      </AppText>
      <AppText variant="bodySmall" tone="secondary" center>
        {message}
      </AppText>
      {onRetry ? (
        <PrimaryButton
          label={retryLabel}
          onPress={onRetry}
          loading={retrying}
          fullWidth={false}
          icon="refresh"
          style={styles.action}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  title: {
    marginTop: spacing.sm,
  },
  action: {
    marginTop: spacing.lg,
  },
});
