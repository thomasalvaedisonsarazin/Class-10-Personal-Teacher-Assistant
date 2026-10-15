import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import type { ComponentProps } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui';
import { MIN_TOUCH_TARGET, palette, radius, spacing } from '@/theme';
import type { TopicItem, TopicStatus } from '@/types/curriculum';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

const STATUS_UI: Record<TopicStatus, { icon: IconName; color: string; label: string }> = {
  completed: { icon: 'check-circle', color: palette.success, label: 'Passed' },
  active: { icon: 'play-circle', color: palette.primary, label: 'In progress' },
  available: { icon: 'circle-outline', color: palette.primary, label: 'Start here' },
  locked: { icon: 'lock', color: palette.locked, label: 'Pass the previous topic to unlock' },
};

export interface TopicRowProps {
  topic: TopicItem;
  index: number;
  onPress: () => void;
}

/** One topic in a subject's path. Locked rows are visible but not tappable. */
export function TopicRow({ topic, index, onPress }: TopicRowProps) {
  const ui = STATUS_UI[topic.status];
  const locked = topic.status === 'locked';
  const score =
    topic.status === 'completed' && topic.bestScorePct !== null
      ? ` · Best ${Math.round(topic.bestScorePct)}%`
      : '';

  return (
    <Pressable
      onPress={onPress}
      disabled={locked}
      accessibilityRole="button"
      accessibilityState={{ disabled: locked }}
      accessibilityLabel={`Topic ${index}: ${topic.title}. ${ui.label}${score}`}
      style={({ pressed }) => [styles.row, locked && styles.locked, pressed && styles.pressed]}
      testID={`topic-row-${topic.id}`}
    >
      <MaterialCommunityIcons name={ui.icon} size={26} color={ui.color} />
      <View style={styles.text}>
        <AppText variant="body" tone={locked ? 'secondary' : 'primary'} numberOfLines={2}>
          {index}. {topic.title}
        </AppText>
        <AppText variant="caption" tone="secondary">
          {ui.label}
          {score}
        </AppText>
      </View>
      {!locked ? (
        <MaterialCommunityIcons name="chevron-right" size={24} color={palette.textSecondary} />
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: MIN_TOUCH_TARGET + spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: palette.surface,
  },
  locked: {
    backgroundColor: palette.surfaceMuted,
  },
  pressed: {
    opacity: 0.85,
  },
  text: {
    flex: 1,
    gap: spacing.xxs,
  },
});
