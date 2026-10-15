import { useEvent, useEventListener } from 'expo';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';

import { palette, radius } from '@/theme';

export interface VideoLessonPlayerProps {
  videoUrl: string;
  onProgress: (watchedSec: number, completed: boolean) => void;
}

/** The rendered slide video with the platform's own controls. */
export function VideoLessonPlayer({ videoUrl, onProgress }: VideoLessonPlayerProps) {
  const player = useVideoPlayer(videoUrl, (p) => {
    p.timeUpdateEventInterval = 15;
  });
  const timeUpdate = useEvent(player, 'timeUpdate');

  useEffect(() => {
    if (timeUpdate && timeUpdate.currentTime > 0) onProgress(timeUpdate.currentTime, false);
  }, [timeUpdate, onProgress]);

  useEventListener(player, 'playToEnd', () => onProgress(player.duration, true));

  return (
    <View style={styles.frame} testID="video-lesson-player">
      <VideoView player={player} style={styles.video} nativeControls contentFit="contain" />
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    borderRadius: radius.lg,
    overflow: 'hidden',
    backgroundColor: palette.textPrimary,
  },
  video: {
    width: '100%',
    aspectRatio: 16 / 9,
  },
});
