import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { HelperText } from 'react-native-paper';

import { SubjectTestResultView } from '@/components/exam/SubjectTestResultView';
import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ChoiceList, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { parseIdParam, useSubject } from '@/hooks/useCurriculum';
import { examKeys } from '@/hooks/useExam';
import { getApiErrorMessage } from '@/services/api';
import { examService } from '@/services/examService';
import { palette, radius, spacing } from '@/theme';
import type { SubjectTestResult } from '@/types/exam';

export default function SubjectTestScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { subjectId: rawSubjectId } = useLocalSearchParams<{ subjectId: string }>();
  const subjectId = parseIdParam(rawSubjectId);
  const subjectQuery = useSubject(subjectId);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<SubjectTestResult | null>(null);

  const testQuery = useQuery({
    queryKey: ['subject-test', subjectId],
    queryFn: () => examService.startSubjectTest(subjectId),
    enabled: Number.isInteger(subjectId) && subjectId > 0,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });

  const submit = useMutation({
    mutationFn: () => {
      const test = testQuery.data;
      if (!test) throw new Error('No test loaded');
      return examService.submitSubjectTest(
        test.testId,
        test.questions.map((q) => ({ questionId: q.questionId, answer: answers[q.questionId] ?? null })),
      );
    },
    onSuccess: async (graded) => {
      setResult(graded);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: examKeys.overview(subjectId) }),
        queryClient.invalidateQueries({ queryKey: ['streak'] }),
      ]);
    },
  });

  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));
  const startNewTest = (): void => {
    setResult(null);
    setAnswers({});
    setIndex(0);
    queryClient.removeQueries({ queryKey: ['subject-test', subjectId] });
    void testQuery.refetch();
  };

  const header = <AppHeader title="Full-subject test" subtitle={subjectQuery.data?.name} onBack={goBack} />;

  if (result) {
    return (
      <Screen padded={false} testID="subject-test-screen">
        {header}
        <Screen scroll edges={['bottom']}>
          <View style={styles.content}>
            <SubjectTestResultView
              result={result}
              onReviseTopic={(id) => router.push({ pathname: '/topic/[id]', params: { id: String(id) } })}
              onRetry={startNewTest}
              onDone={goBack}
            />
          </View>
        </Screen>
      </Screen>
    );
  }

  if (testQuery.isPending || testQuery.isFetching) {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView message="Mixing questions from every topic you passed" />
      </Screen>
    );
  }

  if (testQuery.isError) {
    return (
      <Screen padded={false}>
        {header}
        <ErrorState
          title="Test not ready"
          message={getApiErrorMessage(testQuery.error)}
          onRetry={goBack}
          retryLabel="Go back"
        />
      </Screen>
    );
  }

  const test = testQuery.data;
  const total = test.questions.length;
  const question = test.questions[index];
  const answeredCount = test.questions.filter((q) => answers[q.questionId] !== undefined).length;
  const isLast = index === total - 1;

  return (
    <Screen padded={false} testID="subject-test-screen">
      {header}
      <Screen scroll edges={['bottom']}>
        <View style={styles.content}>
          <AppText variant="caption" tone="secondary">
            Question {index + 1} of {total}
          </AppText>
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
                testID="subject-test-options"
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
                testID="subject-test-submit"
              />
            ) : (
              <PrimaryButton
                label="Next"
                fullWidth={false}
                style={styles.navButton}
                onPress={() => setIndex((i) => Math.min(i + 1, total - 1))}
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
