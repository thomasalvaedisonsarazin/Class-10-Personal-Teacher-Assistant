import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, StyleSheet, View } from 'react-native';
import { IconButton } from 'react-native-paper';

import { AppText } from '@/components/ui';
import { MIN_TOUCH_TARGET, palette, radius, spacing } from '@/theme';
import type { Lesson, Slide } from '@/types/lessons';

import { AnimatedSlide } from './AnimatedSlide';

const SKIP_SECONDS = 10;
const SAVE_EVERY_SECONDS = 15;

export interface AudioLessonPlayerProps {
  lesson: Lesson;
  accent: string;
  /** Called periodically and when the audio finishes. */
  onProgress: (watchedSec: number, completed: boolean) => void;
}

function currentSlideIndex(slides: Slide[], time: number): number {
  let index = 0;
  slides.forEach((slide, i) => {
    if (time >= slide.startSec) index = i;
  });
  return index;
}

/** Same rule as the server video: bullet k of n appears at slideDuration * k / (n + 1). */
function visibleBulletCount(slide: Slide, slideEnd: number, time: number, finished: boolean): number {
  if (finished) return slide.bullets.length;
  const duration = Math.max(slideEnd - slide.startSec, 0.1);
  const elapsed = time - slide.startSec;
  const n = slide.bullets.length;
  let count = 0;
  for (let k = 1; k <= n; k += 1) {
    if (elapsed >= (duration * k) / (n + 1)) count = k;
  }
  return count;
}

function useReduceMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    let active = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => {
        if (active) setReduce(value);
      })
      .catch(() => undefined);
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => {
      active = false;
      sub.remove();
    };
  }, []);
  return reduce;
}

function formatTime(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, '0')}`;
}

/** Narrated slides: the slide on screen follows the audio. */
export function AudioLessonPlayer({ lesson, accent, onProgress }: AudioLessonPlayerProps) {
  const player = useAudioPlayer(lesson.audioUrl ?? null);
  const status = useAudioPlayerStatus(player);
  const lastSaved = useRef(0);
  const finishedSaved = useRef(false);

  const slides = lesson.slides;
  const index = currentSlideIndex(slides, status.currentTime);
  const slide = slides[index];
  const duration = status.duration || lesson.durationSec || 0;
  const reduceMotion = useReduceMotion();
  const slideEnd = slides[index + 1]?.startSec ?? duration;
  const atEnd = duration > 0 && status.currentTime >= duration - 0.3;
  const visibleBullets = slide ? visibleBulletCount(slide, slideEnd, status.currentTime, atEnd) : 0;

  useEffect(() => {
    if (status.didJustFinish && !finishedSaved.current) {
      finishedSaved.current = true;
      onProgress(duration, true);
    } else if (status.currentTime - lastSaved.current >= SAVE_EVERY_SECONDS) {
      lastSaved.current = status.currentTime;
      onProgress(status.currentTime, false);
    }
  }, [status.currentTime, status.didJustFinish, duration, onProgress]);

  const togglePlay = (): void => {
    if (status.playing) {
      player.pause();
      return;
    }
    if (duration > 0 && status.currentTime >= duration - 0.5) {
      void player.seekTo(0);
    }
    player.play();
  };

  const seekBy = (delta: number): void => {
    const target = Math.min(Math.max(status.currentTime + delta, 0), duration || status.currentTime);
    void player.seekTo(target);
  };

  const goToSlide = (target: number): void => {
    const next = slides[target];
    if (next) void player.seekTo(next.startSec);
  };

  const progress = duration > 0 ? Math.min(status.currentTime / duration, 1) : 0;

  return (
    <View style={styles.container} testID="audio-lesson-player">
      {slide ? (
        <AnimatedSlide
          slide={slide}
          index={index}
          total={slides.length}
          visibleBullets={visibleBullets}
          accent={accent}
          reduceMotion={reduceMotion}
          elapsed={atEnd ? slideEnd - slide.startSec : Math.max(status.currentTime - slide.startSec, 0)}
          duration={Math.max(slideEnd - slide.startSec, 0.1)}
          playing={status.playing}
        />
      ) : null}
      {!status.playing && status.currentTime < 0.5 ? (
        <AppText variant="caption" tone="secondary" center>
          Press play — the story unfolds with the voice.
        </AppText>
      ) : null}

      <View style={styles.track} accessibilityElementsHidden importantForAccessibility="no">
        <View style={[styles.fill, { width: `${Math.round(progress * 100)}%`, backgroundColor: accent }]} />
      </View>
      <View style={styles.timeRow}>
        <AppText variant="caption" tone="secondary">
          {formatTime(status.currentTime)}
        </AppText>
        <AppText variant="caption" tone="secondary">
          {formatTime(duration)}
        </AppText>
      </View>

      <View style={styles.controls}>
        <IconButton icon="skip-previous" size={28} onPress={() => goToSlide(index - 1)} disabled={index === 0} accessibilityLabel="Previous slide" />
        <IconButton icon="rewind-10" size={28} onPress={() => seekBy(-SKIP_SECONDS)} accessibilityLabel="Back 10 seconds" />
        <IconButton
          icon={status.playing ? 'pause' : 'play'}
          mode="contained"
          size={40}
          containerColor={accent}
          iconColor={palette.onColor}
          onPress={togglePlay}
          disabled={!status.isLoaded}
          accessibilityLabel={status.playing ? 'Pause' : 'Play'}
          testID="lesson-play"
        />
        <IconButton icon="fast-forward-10" size={28} onPress={() => seekBy(SKIP_SECONDS)} accessibilityLabel="Forward 10 seconds" />
        <IconButton
          icon="skip-next"
          size={28}
          onPress={() => goToSlide(index + 1)}
          disabled={index >= slides.length - 1}
          accessibilityLabel="Next slide"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
  },
  track: {
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: palette.outline,
    overflow: 'hidden',
    marginTop: spacing.sm,
  },
  fill: {
    height: '100%',
  },
  timeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  controls: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: MIN_TOUCH_TARGET,
  },
});
