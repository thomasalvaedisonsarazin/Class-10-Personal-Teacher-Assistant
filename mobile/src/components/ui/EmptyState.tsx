import { StyleSheet, View } from 'react-native';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import type { ComponentProps } from 'react';

import { palette, spacing } from '@/theme';

import { AppText } from './AppText';
import { PrimaryButton } from './PrimaryButton';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

export interface EmptyStateProps {
  title: string;
  message?: string;
  icon?: IconName;
  actionLabel?: string;
  onAction?: () => void;
  testID?: string;
}

export function EmptyState({
  title,
  message,
  icon = 'book-open-variant',
  actionLabel,
  onAction,
  testID,
}: EmptyStateProps) {
  return (
    <View style={styles.container} testID={testID}>
      <MaterialCommunityIcons name={icon} size={48} color={palette.textSecondary} />
      <AppText variant="subtitle" center style={styles.title}>
        {title}
      </AppText>
      {message ? (
        <AppText variant="bodySmall" tone="secondary" center>
          {message}
        </AppText>
      ) : null}
      {actionLabel && onAction ? (
        <PrimaryButton
          label={actionLabel}
          onPress={onAction}
          mode="outlined"
          fullWidth={false}
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
