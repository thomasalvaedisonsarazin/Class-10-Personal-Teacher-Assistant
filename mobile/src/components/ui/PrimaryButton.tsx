import { StyleSheet } from 'react-native';
import type { StyleProp, ViewStyle } from 'react-native';
import { Button } from 'react-native-paper';

import { MIN_TOUCH_TARGET, radius, spacing } from '@/theme';

export type PrimaryButtonMode = 'contained' | 'outlined' | 'text';

export interface PrimaryButtonProps {
  label: string;
  onPress: () => void;
  mode?: PrimaryButtonMode;
  loading?: boolean;
  disabled?: boolean;
  icon?: string;
  /** Override the fill colour (e.g. success / warning). Solid colours only. */
  color?: string;
  fullWidth?: boolean;
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
  testID?: string;
}

export function PrimaryButton({
  label,
  onPress,
  mode = 'contained',
  loading = false,
  disabled = false,
  icon,
  color,
  fullWidth = true,
  style,
  accessibilityLabel,
  testID,
}: PrimaryButtonProps) {
  return (
    <Button
      mode={mode}
      onPress={onPress}
      loading={loading}
      disabled={disabled || loading}
      icon={icon}
      buttonColor={mode === 'contained' ? color : undefined}
      textColor={mode !== 'contained' ? color : undefined}
      style={[styles.button, fullWidth && styles.fullWidth, style]}
      contentStyle={styles.content}
      labelStyle={styles.label}
      accessibilityLabel={accessibilityLabel ?? label}
      testID={testID}
    >
      {label}
    </Button>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: radius.md,
  },
  fullWidth: {
    alignSelf: 'stretch',
  },
  content: {
    minHeight: MIN_TOUCH_TARGET,
    paddingHorizontal: spacing.sm,
  },
  label: {
    fontSize: 16,
    letterSpacing: 0.2,
  },
});
