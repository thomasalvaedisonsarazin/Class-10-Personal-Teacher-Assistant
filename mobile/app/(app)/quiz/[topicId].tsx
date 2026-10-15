import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { HelperText } from 'react-native-paper';

import { QuizResultView } from '@/components/quiz/QuizResultView';
import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ChoiceList, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { curriculumKeys, parseIdParam, useTopic } from '@/hooks/useCurriculum';
import { getApiErrorCode, getApiErrorMessage } from '@/services/api';
import { quizService } from '@/services/quizService';
import { palette, radius, spacing } from '@/theme';
import type { QuizResult } from '@/types/quiz';

export default function QuizScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { topicId: rawTopicId } = useLocalSearchParams<{ topicId: string }>();
  const topicId = parseIdParam(rawTopicId);
  const topicQuery = useTopic(topicId);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<QuizResult | null>(null);

  const attemptQuery = useQuery({
    queryKey: ['quiz', topicId],
    queryFn: () => quizService.startAttempt(topicId),
    enabled: Number.isInteger(topicId) && topicId > 0,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });

  const submit = useMutation({
    mutationFn: () => {
      const attempt = attemptQuery.data;
      if (!attempt) throw new Error('No test loaded');
      return quizService.submitAttempt(
        attempt.attemptId,
        attempt.questions.map((q) => ({ questionId: q.questionId, answer: answers[q.questionId] ?? null })),
      );
    },
    onSuccess: async (graded) => {
      setResult(graded);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: curriculumKeys.subjects }),
        queryClient.invalidateQueries({ queryKey: ['topics'] }),
        queryClient.invalidateQueries({ queryKey: ['streak'] }),
      ]);
    },
  });

  const subjectId = topicQuery.data?.subject.id;
  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));
  const toSubject = (): void => {
    if (subjectId) router.replace({ pathname: '/subject/[id]', params: { id: String(subjectId) } });
    else goBack();
  };

  const startNewTest = (): void => {
    setResult(null);
    setAnswers({});
    setIndex(0);
    queryClient.removeQueries({ queryKey: ['quiz', topicId] });
    void attemptQuery.refetch();
  };

  const header = <AppHeader title="Test" subtitle={topicQuery.data?.title} onBack={goBack} />;

  if (result) {
    return (
      <Screen padded={false} testID="quiz-screen">
        {header}
        <Screen scroll edges={['bottom']}>
          <View style={styles.content}>
            <QuizResultView
              result={result}
              onNextTopic={(id) => router.replace({ pathname: '/topic/[id]', params: { id: String(id) } })}
              onRetry={startNewTest}
              onReviewLesson={() =>
                router.replace({ pathname: '/lesson/[topicId]', params: { topicId: String(topicId) } })
              }
              onBackToSubject={toSubject}
            />
          </View>
        </Screen>
      </Screen>
    );
  }

  if (attemptQuery.isPending || attemptQuery.isFetching) {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView message="Preparing a fresh test for you" />
      </Screen>
    );
  }

  if (attemptQuery.isError) {
    const locked = getApiErrorCode(attemptQuery.error) === 'topic_locked';
    return (
      <Screen padded={false}>
        {header}
        <ErrorState
          title={locked ? 'This topic is locked' : 'Test not ready'}
          message={getApiErrorMessage(attemptQuery.error)}
          onRetry={locked ? goBack : () => void attemptQuery.refetch()}
          retryLabel={locked ? 'Go back' : undefined}
        />
      </Screen>
    );
  }

  const attempt = attemptQuery.data;
  const total = attempt.questions.length;
  const question = attempt.questions[index];
  const answeredCount = attempt.questions.filter((q) => answers[q.questionId] !== undefined).length;
  const isLast = index === total - 1;

  return (
    <Screen padded={false} testID="quiz-screen">
      {header}
      <Screen scroll edges={['bottom']}>
        <View style={styles.content}>
          <View style={styles.progressRow}>
            <AppText variant="caption" tone="secondary">
              Question {index + 1} of {total}
            </AppText>
            <AppText variant="caption" tone="secondary">
              Pass mark {attempt.passPct}%
            </AppText>
          </View>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${Math.round(((index + 1) / total) * 100)}%` }]} />
          </View>

          {question ? (
            <>
              <AppText variant="title">{question.stem}</AppText>
              <ChoiceList
                options={question.options.map((option) => ({ value: option, label: option }))}
                value={answers[question.questionId] ?? null}
                onChange={(value) => setAnswers((prev) => ({ ...prev, [question.questionId]: value }))}
                testID="quiz-options"
              />
            </>
          ) : null}

          <View style={styles.nav}>
            <PrimaryButton
              label="Back"
              mode="outlined"
              fullWidth={false}
              style={styles.navButton}
              onPress={() => setIndex((i) => Math.max(i - 1, 0))}
              disabled={index === 0}
            />
            {isLast ? (
              <PrimaryButton
                label="Submit test"
                icon="check"
                fullWidth={false}
                style={styles.navButton}
                onPress={() => submit.mutate()}
                loading={submit.isPending}
                testID="quiz-submit"
              />
            ) : (
              <PrimaryButton
                label="Next"
                fullWidth={false}
                style={styles.navButton}
                onPress={() => setIndex((i) => Math.min(i + 1, total - 1))}
                testID="quiz-next"
              />
            )}
          </View>

          {isLast && answeredCount < total ? (
            <HelperText type="info" visible>
              {total - answeredCount} question(s) not answered — they will count as wrong.
            </HelperText>
          ) : null}
          {submit.isError ? (
            <HelperText type="error" visible>
              {getApiErrorMessage(submit.error)}
            </HelperText>
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
  progressRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  track: {
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: palette.outline,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    backgroundColor: palette.primary,
  },
  nav: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  navButton: {
    flex: 1,
  },
});
