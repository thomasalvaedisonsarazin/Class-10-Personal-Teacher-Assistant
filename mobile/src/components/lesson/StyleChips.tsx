import { ScrollView, StyleSheet } from 'react-native';
import { Chip } from 'react-native-paper';

import { MIN_TOUCH_TARGET, palette, spacing } from '@/theme';
import type { LessonStyle } from '@/types/lessons';

/** Story first, then the other ways of explaining the same topic. */
export const STYLE_CHOICES: { style: LessonStyle; label: string; icon: string }[] = [
  { style: 'story', label: 'Story', icon: 'book-open-page-variant-outline' },
  { style: 'analogy', label: 'Analogy', icon: 'swap-horizontal' },
  { style: 'step_by_step', label: 'Step by step', icon: 'stairs' },
  { style: 'real_life', label: 'Real life', icon: 'storefront-outline' },
  { style: 'worked_example', label: 'Worked examples', icon: 'pencil-outline' },
  { style: 'visual', label: 'Picture it', icon: 'image-outline' },
  { style: 'base', label: 'Standard', icon: 'school-outline' },
];

export interface StyleChipsProps {
  current: LessonStyle | null;
  disabled?: boolean;
  onSelect: (style: LessonStyle) => void;
}

/** Horizontal list of explanation styles; the student can switch any time. */
export function StyleChips({ current, disabled = false, onSelect }: StyleChipsProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
      accessibilityLabel="Choose how to explain this topic"
      testID="style-chips"
    >
      {STYLE_CHOICES.map(({ style, label, icon }) => {
        const selected = style === current;
        return (
          <Chip
            key={style}
            icon={icon}
            selected={selected}
            showSelectedCheck={false}
            disabled={disabled && !selected}
            onPress={() => {
              if (!selected) onSelect(style);
            }}
            style={[styles.chip, selected && styles.selected]}
            textStyle={selected ? styles.selectedText : undefined}
            accessibilityState={{ selected, disabled }}
            testID={`style-chip-${style}`}
          >
            {label}
          </Chip>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  chip: {
    minHeight: MIN_TOUCH_TARGET - 8,
    justifyContent: 'center',
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.outline,
  },
  selected: {
    backgroundColor: palette.primary,
    borderColor: palette.primary,
  },
  selectedText: {
    color: palette.onColor,
  },
});
