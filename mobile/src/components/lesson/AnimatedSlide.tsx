import { useEffect, useState } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui';
import { motion, palette, radius, spacing } from '@/theme';
import type { Slide } from '@/types/lessons';

import { StoryImage } from './StoryImage';

const ENTER_MS = 420;
const BULLET_MS = 320;
const ENTER_OFFSET = 14;

export interface AnimatedSlideProps {
  slide: Slide;
  index: number;
  total: number;
  /** How many bullets have been "spoken" so far (they appear one by one). */
  visibleBullets: number;
  accent: string;
  reduceMotion: boolean;
  /** Seconds since the slide started, and the slide length (drive the scene motions). */
  elapsed: number;
  duration: number;
  playing: boolean;
}

interface AnimatedBulletProps {
  text: string;
  visible: boolean;
  accent: string;
  reduceMotion: boolean;
}

/** A bullet that fades and slides in when the narration reaches it. */
function AnimatedBullet({ text, visible, accent, reduceMotion }: AnimatedBulletProps) {
  const [progress] = useState(() => new Animated.Value(visible ? 1 : 0));

  useEffect(() => {
    if (reduceMotion) {
      progress.setValue(visible ? 1 : 0);
      return;
    }
    Animated.timing(progress, {
      toValue: visible ? 1 : 0,
      duration: visible ? BULLET_MS : motion.fast,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [visible, progress, reduceMotion]);

  return (
    <Animated.View
      style={[
        styles.bulletRow,
        {
          opacity: progress,
          transform: [{ translateX: progress.interpolate({ inputRange: [0, 1], outputRange: [-ENTER_OFFSET, 0] }) }],
        },
      ]}
      accessibilityElementsHidden={!visible}
      importantForAccessibility={visible ? 'auto' : 'no-hide-descendants'}
    >
      <View style={[styles.dot, { backgroundColor: accent }]} />
      <AppText style={styles.bulletText}>{text}</AppText>
    </Animated.View>
  );
}

/**
 * One story scene: the card fades up, the emoji "scene picture" pops in gently,
 * then bullets appear in time with the voice. Flat colours only.
 */
export function AnimatedSlide({
  slide,
  index,
  total,
  visibleBullets,
  accent,
  reduceMotion,
  elapsed,
  duration,
  playing,
}: AnimatedSlideProps) {
  const hasPicture = Boolean(slide.imageUrl);
  const [enter] = useState(() => new Animated.Value(reduceMotion ? 1 : 0));

  useEffect(() => {
    if (reduceMotion) {
      enter.setValue(1);
      return;
    }
    enter.setValue(0);
    Animated.timing(enter, {
      toValue: 1,
      duration: ENTER_MS,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [index, enter, reduceMotion]);

  const emojiScale = enter.interpolate({ inputRange: [0, 0.6, 1], outputRange: [0.6, 1.08, 1] });

  return (
    <Animated.View
      style={[
        styles.card,
        { borderTopColor: accent },
        {
          opacity: enter,
          transform: [{ translateY: enter.interpolate({ inputRange: [0, 1], outputRange: [ENTER_OFFSET, 0] }) }],
        },
      ]}
      testID="lesson-slide"
    >
      <View style={styles.header}>
        <View style={styles.headerText}>
          <AppText variant="caption" tone="secondary">
            Scene {index + 1} of {total}
          </AppText>
          <AppText variant="title">{slide.heading}</AppText>
        </View>
        {slide.emoji && !hasPicture ? (
          <Animated.View
            style={[styles.emojiBubble, { borderColor: accent, transform: [{ scale: emojiScale }] }]}
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
          >
            <AppText style={styles.emoji}>{slide.emoji}</AppText>
          </Animated.View>
        ) : null}
      </View>
      {hasPicture && slide.imageUrl ? (
        <StoryImage
          uri={slide.imageUrl}
          index={index}
          elapsed={elapsed}
          duration={duration}
          playing={playing}
          reduceMotion={reduceMotion}
          accessibilityLabel={`Illustration: ${slide.heading}`}
        />
      ) : null}
      {slide.bullets.map((bullet, i) => (
        <AnimatedBullet
          key={`${index}-${bullet}`}
          text={bullet}
          visible={i < visibleBullets}
          accent={accent}
          reduceMotion={reduceMotion}
        />
      ))}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: 240,
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderTopWidth: 6,
    backgroundColor: palette.surface,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    marginBottom: spacing.xs,
  },
  headerText: {
    flex: 1,
    gap: spacing.xs,
  },
  emojiBubble: {
    width: 72,
    height: 72,
    borderRadius: radius.pill,
    borderWidth: 2,
    backgroundColor: palette.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emoji: {
    fontSize: 38,
    lineHeight: 46,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: radius.pill,
    marginTop: 9,
  },
  bulletText: {
    flex: 1,
  },
});
