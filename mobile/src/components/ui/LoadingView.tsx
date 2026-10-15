import { StyleSheet, View } from 'react-native';
import { ActivityIndicator } from 'react-native-paper';

import { palette, spacing } from '@/theme';

import { AppText } from './AppText';

export interface LoadingViewProps {
  message?: string;
  fullScreen?: boolean;
  testID?: string;
}

export function LoadingView({ message, fullScreen = true, testID }: LoadingViewProps) {
  return (
    <View
      style={[styles.container, fullScreen && styles.fullScreen]}
      accessibilityRole="progressbar"
      accessibilityLabel={message ?? 'Loading'}
      testID={testID}
    >
      <ActivityIndicator size="large" color={palette.primary} />
      {message ? (
        <AppText variant="bodySmall" tone="secondary" center>
          {message}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    gap: spacing.md,
  },
  fullScreen: {
    flex: 1,
    backgroundColor: palette.background,
  },
});
