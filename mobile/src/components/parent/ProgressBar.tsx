import { StyleSheet, View } from 'react-native';

import { palette, radius } from '@/theme';

export interface ProgressBarProps {
  value: number;
  total: number;
  color: string;
}

/** Flat progress bar (no gradients). */
export function ProgressBar({ value, total, color }: ProgressBarProps) {
  const pct = total > 0 ? Math.min(Math.max(value / total, 0), 1) : 0;
  return (
    <View
      style={styles.track}
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: total, now: value }}
    >
      <View style={[styles.fill, { width: `${Math.round(pct * 100)}%`, backgroundColor: color }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: palette.outline,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: radius.pill,
  },
});
