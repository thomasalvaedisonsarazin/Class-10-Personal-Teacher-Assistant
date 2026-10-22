import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { StyleSheet, View } from 'react-native';

import { AnswerReview } from '@/components/quiz/AnswerReview';
import { AppText, PrimaryButton } from '@/components/ui';
import { palette, radius, spacing } from '@/theme';
import type { QuizResult } from '@/types/quiz';

export interface QuizResultViewProps {
  result: QuizResult;
  onNextTopic: (topicId: number) => void;
  onRetry: () => void;
  onReviewLesson: () => void;
  onBackToSubject: () => void;
}

/** Score, pass/fail message, next steps, and every answer with its explanation. */
export function QuizResultView({ result, onNextTopic, onRetry, onReviewLesson, onBackToSubject }: QuizResultViewProps) {
  const color = result.passed ? palette.success : palette.warning;

  return (
    <View style={styles.container} testID="quiz-result">
      <View style={[styles.scoreCard, { backgroundColor: color }]}>
        <MaterialCommunityIcons name={result.passed ? 'check-decagram' : 'refresh'} size={40} color={palette.onColor} />
        <AppText variant="display" tone="inverse">
          {Math.round(result.scorePct)}%
        </AppText>
        <AppText tone="inverse" center>
          {result.correctCount} of {result.total} correct ·{' '}
          {result.passed
            ? 'Passed! Well done.'
            : `You need ${result.passPct}% to pass. Try again with new questions.`}
        </AppText>
      </View>

      <View style={styles.actions}>
        {result.passed && result.nextTopic ? (
          <PrimaryButton
            label={`Next topic: ${result.nextTopic.title}`}
            icon="arrow-right"
            onPress={() => onNextTopic(result.nextTopic?.id ?? 0)}
            testID="quiz-next-topic"
          />
        ) : null}
        {result.passed && !result.nextTopic ? (
          <AppText tone="success" center>
            You have finished every topic in this subject!
          </AppText>
        ) : null}
        {!result.passed ? (
          <>
            <PrimaryButton label="Watch the lesson again" icon="play" onPress={onReviewLesson} testID="quiz-review-lesson" />
            <PrimaryButton label="Try a new test" icon="refresh" mode="outlined" onPress={onRetry} testID="quiz-retry" />
          </>
        ) : null}
        <PrimaryButton label="Back to subject" mode="text" onPress={onBackToSubject} />
      </View>

      <AnswerReview results={result.results} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.lg,
  },
  scoreCard: {
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.xl,
    borderRadius: radius.lg,
  },
  actions: {
    gap: spacing.md,
  },
});
