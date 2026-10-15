import { StyleSheet, View } from 'react-native';
import { ActivityIndicator } from 'react-native-paper';

import { AppText } from '@/components/ui';
import { palette, radius, spacing } from '@/theme';

export interface GeneratingViewProps {
  styleLabel: string | null;
  /** True for a "Not clear" re-explanation, false for the first lesson. */
  isReExplanation: boolean;
}

/** Calm waiting state while the AI prepares a lesson (no flashy animation). */
export function GeneratingView({ styleLabel, isReExplanation }: GeneratingViewProps) {
  return (
    <View style={styles.box} accessibilityRole="progressbar" testID="lesson-generating">
      <ActivityIndicator size="large" color={palette.primary} />
      <AppText variant="subtitle" center>
        {isReExplanation ? 'Preparing a new explanation' : 'Preparing your lesson'}
      </AppText>
      {styleLabel ? (
        <AppText tone="accent" center>
          {styleLabel}
        </AppText>
      ) : null}
      <AppText variant="bodySmall" tone="secondary" center>
        We are writing the story, recording the voice and drawing the pictures. This takes
        about a minute or two, and only happens the first time anyone opens this lesson.
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    gap: spacing.md,
    alignItems: 'center',
    padding: spacing.xl,
    borderRadius: radius.lg,
    backgroundColor: palette.surface,
  },
});
