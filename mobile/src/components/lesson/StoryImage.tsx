import { Image } from 'expo-image';
import { useEffect, useState } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';

import { palette, radius } from '@/theme';

const ZOOM = 0.08; // the picture slowly zooms in by 8% over the scene
const PAN = 14; // odd scenes also drift sideways (dp)

export interface StoryImageProps {
  uri: string;
  index: number;
  /** Seconds into the scene and its length; the camera move follows the narration. */
  elapsed: number;
  duration: number;
  playing: boolean;
  reduceMotion: boolean;
  accessibilityLabel: string;
}

/** A storybook illustration with a gentle "Ken Burns" pan/zoom synced to the voice. */
export function StoryImage({ uri, index, elapsed, duration, playing, reduceMotion, accessibilityLabel }: StoryImageProps) {
  const [progress] = useState(() => new Animated.Value(0));
  const fraction = duration > 0 ? Math.min(Math.max(elapsed / duration, 0), 1) : 0;

  useEffect(() => {
    if (reduceMotion) {
      progress.setValue(0);
      return undefined;
    }
    progress.setValue(fraction);
    if (!playing) return undefined;
    const animation = Animated.timing(progress, {
      toValue: 1,
      duration: Math.max((1 - fraction) * duration * 1000, 0),
      easing: Easing.linear,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
    // Re-sync only when the scene changes or play/pause toggles (not every audio tick).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, playing, reduceMotion, duration]);

  const scale = progress.interpolate({ inputRange: [0, 1], outputRange: [1, 1 + ZOOM] });
  const translateX = progress.interpolate({
    inputRange: [0, 1],
    outputRange: index % 2 ? [-PAN, PAN] : [0, 0],
  });

  return (
    <View style={styles.frame}>
      <Animated.View style={[styles.fill, { transform: [{ scale }, { translateX }] }]}>
        <Image
          source={{ uri }}
          style={styles.fill}
          contentFit="cover"
          transition={300}
          accessibilityLabel={accessibilityLabel}
        />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    width: '100%',
    aspectRatio: 3 / 2,
    borderRadius: radius.md,
    overflow: 'hidden',
    backgroundColor: palette.surfaceMuted,
  },
  fill: {
    width: '100%',
    height: '100%',
  },
});
