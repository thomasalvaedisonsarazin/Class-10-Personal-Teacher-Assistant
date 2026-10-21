import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { HelperText, SegmentedButtons } from 'react-native-paper';

import { AudioLessonPlayer } from '@/components/lesson/AudioLessonPlayer';
import { GeneratingView } from '@/components/lesson/GeneratingView';
import { LanguageToggle } from '@/components/lesson/LanguageToggle';
import { DownloadButton, OfflineFallback } from '@/components/lesson/OfflineControls';
import { StyleChips } from '@/components/lesson/StyleChips';
import { VideoLessonPlayer } from '@/components/lesson/VideoLessonPlayer';
import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { parseIdParam, useTopic } from '@/hooks/useCurriculum';
import { useLessonFlow } from '@/hooks/useLessonFlow';
import { getApiErrorCode, getApiErrorMessage } from '@/services/api';
import { lessonService } from '@/services/lessonService';
import { palette, radius, safeTileColor, spacing } from '@/theme';
import type { LessonStyle } from '@/types/lessons';

type ViewMode = 'slides' | 'video';

export default function LessonScreen() {
  const router = useRouter();
  const { topicId: rawTopicId } = useLocalSearchParams<{ topicId: string }>();
  const topicId = parseIdParam(rawTopicId);
  const topicQuery = useTopic(topicId);
  const { user, refreshUser } = useAuth();
  const flow = useLessonFlow(topicId, () => void refreshUser());
  const [mode, setMode] = useState<ViewMode>('slides');
  const [marking, setMarking] = useState(false);
  const [askedAgain, setAskedAgain] = useState(false);

  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));
  const accent = safeTileColor(topicQuery.data?.subject.tileColor, 0);
  const lesson = flow.lesson;

  const saveProgress = useCallback(
    (watchedSec: number, completed: boolean) => {
      if (lesson) {
        lessonService.saveProgress(lesson.id, watchedSec, completed).catch(() => undefined);
      }
    },
    [lesson],
  );

  const handleNotClear = (): void => {
    setAskedAgain(true);
    setMode('slides');
    flow.notClear();
  };

  const handleChooseStyle = (style: LessonStyle): void => {
    setAskedAgain(true);
    setMode('slides');
    flow.chooseStyle(style);
  };

  const handleUnderstood = async (): Promise<void> => {
    if (!lesson) return;
    setMarking(true);
    try {
      await lessonService.markClear(topicId, lesson.id);
    } catch {
      // Feedback is optional; never block the student.
    } finally {
      setMarking(false);
      router.replace({
        pathname: '/quiz/[topicId]',
        params: { topicId: String(topicId) },
      });
    }
  };

  const header = <AppHeader title={topicQuery.data?.title ?? 'Lesson'} subtitle={lesson?.styleLabel} onBack={goBack} />;

  if (flow.isLoading) {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView message="Opening your lesson" />
      </Screen>
    );
  }

  if (flow.loadError) {
    const locked = getApiErrorCode(flow.loadError) === 'topic_locked';
    return (
      <Screen padded={false}>
        {header}
        <ErrorState
          title={locked ? 'This topic is locked' : undefined}
          message={getApiErrorMessage(flow.loadError)}
          onRetry={locked ? goBack : flow.reload}
          retryLabel={locked ? 'Go back' : undefined}
        />
        {locked ? null : <OfflineFallback topicId={topicId} />}
      </Screen>
    );
  }

  return (
    <Screen padded={false} testID="lesson-screen">
      {header}
      <Screen scroll edges={['bottom']}>
        <View style={styles.content}>
          {topicQuery.data?.languageFixed ? null : (
            // Language subjects (Tamil) are always taught in their own language.
            <LanguageToggle
              value={lesson?.language ?? user?.lessonLanguage ?? user?.medium ?? null}
              disabled={!lesson || flow.chooseStylePending || flow.notClearPending}
              onChange={(language) => {
                setAskedAgain(true);
                setMode('slides');
                flow.chooseLanguage(language);
              }}
            />
          )}
          <StyleChips
            current={lesson?.style ?? flow.job?.style ?? null}
            disabled={!lesson || flow.chooseStylePending || flow.notClearPending}
            onSelect={handleChooseStyle}
          />
          {flow.failedMessage ? (
            <ErrorState
              title="Lesson not ready"
              message={flow.failedMessage}
              onRetry={askedAgain ? flow.notClear : flow.reload}
            />
          ) : null}

          {!lesson && flow.job && !flow.failedMessage ? (
            <GeneratingView styleLabel={flow.job.styleLabel} isReExplanation={askedAgain} />
          ) : null}

          {lesson ? (
            <>
              <View style={styles.titleBlock}>
                <AppText variant="title">{lesson.title}</AppText>
                <View style={[styles.chip, { borderColor: accent }]}>
                  <AppText variant="caption">{lesson.styleLabel}</AppText>
                </View>
              </View>

              {lesson.videoUrl && lesson.audioUrl ? (
                <SegmentedButtons
                  value={mode}
                  onValueChange={(value) => setMode(value === 'video' ? 'video' : 'slides')}
                  buttons={[
                    {
                      value: 'slides',
                      label: 'Slides + audio',
                      icon: 'presentation',
                    },
                    {
                      value: 'video',
                      label: 'Video',
                      icon: 'play-box-outline',
                    },
                  ]}
                />
              ) : null}

              {lesson.videoUrl && (mode === 'video' || !lesson.audioUrl) ? (
                <VideoLessonPlayer key={lesson.id} videoUrl={lesson.videoUrl} onProgress={saveProgress} />
              ) : (
                <AudioLessonPlayer key={lesson.id} lesson={lesson} accent={accent} onProgress={saveProgress} />
              )}

              <View style={styles.actions}>
                <PrimaryButton
                  label="I understood — take the test"
                  icon="check"
                  color={palette.success}
                  onPress={() => void handleUnderstood()}
                  loading={marking}
                  testID="lesson-understood"
                />
                <PrimaryButton
                  label="Not clear — explain another way"
                  icon="help-circle-outline"
                  mode="outlined"
                  onPress={handleNotClear}
                  loading={flow.notClearPending}
                  testID="lesson-not-clear"
                />
                <DownloadButton
                  lesson={lesson}
                  topicTitle={topicQuery.data?.title ?? lesson.title}
                  subjectName={topicQuery.data?.subject.name ?? ''}
                />
                {flow.notClearError ? (
                  <HelperText type="error" visible>
                    {getApiErrorMessage(flow.notClearError)}
                  </HelperText>
                ) : null}
              </View>
            </>
          ) : null}
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
  titleBlock: {
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  chip: {
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: palette.surface,
  },
  actions: {
    gap: spacing.md,
    marginTop: spacing.sm,
  },
});
