import { useLocalSearchParams, useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { HelperText } from 'react-native-paper';

import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { parseIdParam, useStartTopic, useTopic } from '@/hooks/useCurriculum';
import { getApiErrorCode, getApiErrorMessage } from '@/services/api';
import { palette, radius, spacing } from '@/theme';
import type { TopicStatus } from '@/types/curriculum';

const STATUS_TEXT: Record<TopicStatus, string> = {
  available: 'Not started yet',
  active: 'In progress — take the test when you are ready',
  completed: 'Passed — open any time to revise',
  locked: 'Locked',
};

export default function TopicScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const topicId = parseIdParam(id);
  const topicQuery = useTopic(topicId);
  const startTopic = useStartTopic();
  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));

  if (topicQuery.isPending) {
    return (
      <Screen padded={false}>
        <AppHeader title="Topic" onBack={goBack} />
        <LoadingView />
      </Screen>
    );
  }
  if (topicQuery.isError) {
    const locked = getApiErrorCode(topicQuery.error) === 'topic_locked';
    return (
      <Screen padded={false}>
        <AppHeader title="Topic" onBack={goBack} />
        <ErrorState
          title={locked ? 'This topic is locked' : undefined}
          message={getApiErrorMessage(topicQuery.error)}
          onRetry={locked ? goBack : () => void topicQuery.refetch()}
          retryLabel={locked ? 'Go back' : undefined}
          retrying={topicQuery.isFetching}
        />
      </Screen>
    );
  }

  const topic = topicQuery.data;
  const openLesson = (): void => {
    const go = (): void =>
      router.push({ pathname: '/lesson/[topicId]', params: { topicId: String(topic.id) } });
    if (topic.status === 'available') {
      startTopic.mutate(topic.id, { onSuccess: go });
    } else {
      go();
    }
  };
  const objectives = topic.learningObjectives
    .split(/\r?\n|;\s*/)
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <Screen padded={false} testID="topic-screen">
      <AppHeader title={topic.subject.name} subtitle={topic.chapterTitle} onBack={goBack} />
      <Screen scroll edges={[]}>
        <View style={styles.content}>
          <AppText variant="display">{topic.title}</AppText>

          <View style={[styles.status, { borderLeftColor: topic.subject.tileColor }]}>
            <AppText variant="bodySmall" tone="secondary">
              {STATUS_TEXT[topic.status]}
              {topic.bestScorePct !== null ? ` · Best score ${Math.round(topic.bestScorePct)}%` : ''}
            </AppText>
          </View>

          {objectives.length > 0 ? (
            <View style={styles.section}>
              <AppText variant="subtitle">In this topic you will learn</AppText>
              {objectives.map((line) => (
                <AppText key={line} tone="secondary">
                  • {line}
                </AppText>
              ))}
            </View>
          ) : null}

          <View style={styles.section}>
            <PrimaryButton
              label={topic.status === 'available' ? 'Start lesson' : 'Open lesson'}
              icon="play"
              onPress={openLesson}
              loading={startTopic.isPending}
              testID="start-topic"
            />
            {topic.status !== 'available' ? (
              <PrimaryButton
                label={topic.status === 'completed' ? 'Take the test again' : 'Take the test'}
                icon="clipboard-check-outline"
                mode="outlined"
                onPress={() =>
                  router.push({ pathname: '/quiz/[topicId]', params: { topicId: String(topic.id) } })
                }
                testID="take-test"
              />
            ) : null}
            <HelperText type="info" visible>
              Watch the lesson, then take the test. Score {topic.passPct}% or more to unlock the next
              topic. Every test has new questions.
            </HelperText>
            {startTopic.isError ? (
              <HelperText type="error" visible>
                {getApiErrorMessage(startTopic.error)}
              </HelperText>
            ) : null}
          </View>
        </View>
      </Screen>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.xl,
    paddingVertical: spacing.lg,
  },
  status: {
    borderLeftWidth: 4,
    borderRadius: radius.sm,
    backgroundColor: palette.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  section: {
    gap: spacing.sm,
  },
});
