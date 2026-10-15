import { StyleSheet } from 'react-native';
import type { StyleProp, TextStyle } from 'react-native';
import { Text } from 'react-native-paper';
import type { ReactNode } from 'react';

import { palette } from '@/theme';

export type AppTextVariant = 'display' | 'title' | 'subtitle' | 'body' | 'bodySmall' | 'caption' | 'label';

export type AppTextTone = 'primary' | 'secondary' | 'accent' | 'success' | 'warning' | 'error' | 'inverse';

export interface AppTextProps {
  children: ReactNode;
  variant?: AppTextVariant;
  tone?: AppTextTone;
  center?: boolean;
  numberOfLines?: number;
  style?: StyleProp<TextStyle>;
  testID?: string;
}

const VARIANT_MAP = {
  display: 'headlineMedium',
  title: 'titleLarge',
  subtitle: 'titleMedium',
  body: 'bodyLarge',
  bodySmall: 'bodyMedium',
  caption: 'bodySmall',
  label: 'labelLarge',
} as const;

export function AppText({
  children,
  variant = 'body',
  tone = 'primary',
  center = false,
  numberOfLines,
  style,
  testID,
}: AppTextProps) {
  return (
    <Text
      variant={VARIANT_MAP[variant]}
      numberOfLines={numberOfLines}
      style={[toneStyles[tone], center && styles.center, style]}
      testID={testID}
    >
      {children}
    </Text>
  );
}

const styles = StyleSheet.create({
  center: {
    textAlign: 'center',
  },
});

const toneStyles = StyleSheet.create({
  primary: { color: palette.textPrimary },
  secondary: { color: palette.textSecondary },
  accent: { color: palette.primary },
  success: { color: palette.success },
  warning: { color: palette.warning },
  error: { color: palette.error },
  inverse: { color: palette.onColor },
});
