import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { HelperText } from 'react-native-paper';

import { PrimaryButton } from '@/components/ui';
import { useDeleteDownload, useDownload, useDownloadLesson } from '@/hooks/useDownloads';
import { downloadForTopic, formatSize, offlineSupported } from '@/services/offlineService';
import type { Lesson } from '@/types/lessons';

export interface DownloadButtonProps {
  lesson: Lesson;
  topicTitle: string;
  subjectName: string;
}

/** "Download for offline" / "Saved offline · 4.2 MB — remove". Hidden in the web preview. */
export function DownloadButton({ lesson, topicTitle, subjectName }: DownloadButtonProps) {
  const saved = useDownload(lesson.id);
  const download = useDownloadLesson();
  const remove = useDeleteDownload();
  if (!offlineSupported) return null;

  if (saved.data) {
    return (
      <PrimaryButton
        label={`Saved offline · ${formatSize(saved.data.sizeBytes)} — remove`}
        icon="check-circle-outline"
        mode="text"
        onPress={() => remove.mutate(lesson.id, { onSuccess: () => void saved.refetch() })}
        loading={remove.isPending}
        testID="lesson-remove-download"
      />
    );
  }
  return (
    <>
      <PrimaryButton
        label="Download for offline"
        icon="download-outline"
        mode="text"
        onPress={() =>
          download.mutate({ lesson, topicTitle, subjectName }, { onSuccess: () => void saved.refetch() })
        }
        loading={download.isPending}
        testID="lesson-download"
      />
      {download.isError ? (
        <HelperText type="error" visible>
          {download.error instanceof Error ? download.error.message : 'Download failed.'}
        </HelperText>
      ) : null}
    </>
  );
}

export interface OfflineFallbackProps {
  topicId: number;
}

/** When the lesson can't load (no internet), offer the copy saved on the phone. */
export function OfflineFallback({ topicId }: OfflineFallbackProps) {
  const router = useRouter();
  const saved = useQuery({
    queryKey: ['downloads', 'topic', topicId],
    queryFn: () => downloadForTopic(topicId),
    enabled: offlineSupported,
  });
  if (!saved.data) return null;
  const lessonId = saved.data.lesson.id;
  return (
    <PrimaryButton
      label="Play the copy saved on this phone"
      icon="download-circle-outline"
      onPress={() => router.replace({ pathname: '/offline/[lessonId]', params: { lessonId: String(lessonId) } })}
      testID="lesson-play-offline"
    />
  );
}
