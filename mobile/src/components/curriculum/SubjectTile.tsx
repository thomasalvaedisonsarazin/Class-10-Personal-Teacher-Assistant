import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import type { ComponentProps } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui';
import { MIN_TOUCH_TARGET, palette, radius, spacing } from '@/theme';
import type { SubjectSummary } from '@/types/curriculum';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

export interface SubjectTileProps {
  subject: SubjectSummary;
  color: string;
  onPress: () => void;
}

const FALLBACK_ICON: IconName = 'book-open-variant';

function iconName(name: string): IconName {
  return name in MaterialCommunityIcons.glyphMap ? (name as IconName) : FALLBACK_ICON;
}

/** Flat, solid-colour subject tile with progress and the next topic. */
export function SubjectTile({ subject, color, onPress }: SubjectTileProps) {
  const { totalTopics, completedTopics, currentTopic } = subject;
  const progress = totalTopics > 0 ? completedTopics / totalTopics : 0;
  const nextLabel = currentTopic
    ? `${currentTopic.status === 'active' ? 'Continue' : 'Next'}: ${currentTopic.title}`
    : 'All topics completed';

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${subject.name}. ${completedTopics} of ${totalTopics} topics done. ${nextLabel}`}
      style={({ pressed }) => [styles.tile, { backgroundColor: color }, pressed && styles.pressed]}
      testID={`subject-tile-${subject.id}`}
    >
      <View style={styles.header}>
        <MaterialCommunityIcons name={iconName(subject.icon)} size={28} color={palette.onColor} />
        <AppText variant="caption" tone="inverse">
          {completedTopics}/{totalTopics}
        </AppText>
      </View>
      <AppText variant="subtitle" tone="inverse" numberOfLines={2}>
        {subject.name}
      </AppText>
      <View style={styles.track} accessibilityElementsHidden importantForAccessibility="no">
        <View style={[styles.fill, { width: `${Math.round(progress * 100)}%` }]} />
      </View>
      <AppText variant="caption" tone="inverse" numberOfLines={2}>
        {nextLabel}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    flex: 1,
    minHeight: MIN_TOUCH_TARGET * 3,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  pressed: {
    opacity: 0.88,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  track: {
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(255,255,255,0.35)',
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: radius.pill,
    backgroundColor: palette.onColor,
  },
});
