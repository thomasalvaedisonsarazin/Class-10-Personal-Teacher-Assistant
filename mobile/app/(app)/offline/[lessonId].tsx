import { useLocalSearchParams, useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { AudioLessonPlayer } from '@/components/lesson/AudioLessonPlayer';
import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, Screen } from '@/components/ui';
import { parseIdParam } from '@/hooks/useCurriculum';
import { useDownload } from '@/hooks/useDownloads';
import { palette, radius, spacing } from '@/theme';

/** Plays a downloaded lesson entirely from the phone's storage. */
export default function OfflineLessonScreen() {
  const router = useRouter();
  const { lessonId } = useLocalSearchParams<{ lessonId: string }>();
  const id = parseIdParam(lessonId);
  const saved = useDownload(Number.isInteger(id) ? id : null);
  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/downloads'));

  if (saved.isPending) {
    return (
      <Screen padded={false}>
        <AppHeader title="Saved lesson" onBack={goBack} />
        <LoadingView />
      </Screen>
    );
  }
  if (!saved.data) {
    return (
      <Screen padded={false}>
        <AppHeader title="Saved lesson" onBack={goBack} />
        <ErrorState title="Not found" message="This download was removed." onRetry={goBack} retryLabel="Go back" />
      </Screen>
    );
  }

  const { lesson, topicTitle, subjectName } = saved.data;
  return (
    <Screen padded={false} testID="offline-lesson">
      <AppHeader title={topicTitle} subtitle={`${subjectName} · saved offline`} onBack={goBack} />
      <Screen scroll edges={['bottom']}>
        <View style={styles.content}>
          <View style={styles.note}>
            <AppText variant="caption" tone="secondary">
              Playing from your phone — no internet needed. Take the test when you are back online.
            </AppText>
          </View>
          <AppText variant="title">{lesson.title}</AppText>
          <AudioLessonPlayer lesson={lesson} accent={palette.primary} onProgress={() => undefined} />
        </View>
      </Screen>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.lg,
    paddingVertical: spacing.lg,
  },
  note: {
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: palette.surface,
  },
});
