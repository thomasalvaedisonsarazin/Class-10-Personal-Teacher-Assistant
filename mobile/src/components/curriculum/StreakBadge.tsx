import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui';
import { palette, radius, spacing } from '@/theme';
import type { Streak } from '@/types/curriculum';

export interface StreakBadgeProps {
  streak: Streak;
}

/** "🔥 3-day streak · best 7" — or a gentle nudge when today isn't counted yet. */
export function StreakBadge({ streak }: StreakBadgeProps) {
  const label =
    streak.current > 0
      ? `🔥 ${streak.current}-day streak${streak.longest > streak.current ? ` · best ${streak.longest}` : ''}`
      : 'Start a streak — learn something today';
  const hint = streak.current > 0 && !streak.studiedToday ? 'Study today to keep it going' : null;

  return (
    <View
      style={[styles.badge, streak.studiedToday ? styles.done : styles.pending]}
      accessibilityLabel={hint ? `${label}. ${hint}` : label}
      testID="streak-badge"
    >
      <AppText variant="label">{label}</AppText>
      {hint ? (
        <AppText variant="caption" tone="secondary">
          {hint}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    gap: spacing.xxs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    backgroundColor: palette.surface,
  },
  done: {
    borderColor: palette.success,
  },
  pending: {
    borderColor: palette.warning,
  },
});
