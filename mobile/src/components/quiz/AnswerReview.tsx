import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui';
import { palette, radius, spacing } from '@/theme';
import type { QuestionResult } from '@/types/quiz';

export interface AnswerReviewProps {
  results: (QuestionResult & { topicTitle?: string })[];
}

/** Every answer of a graded test with the correct answer and its explanation. */
export function AnswerReview({ results }: AnswerReviewProps) {
  return (
    <View style={styles.list}>
      <AppText variant="subtitle">Your answers</AppText>
      {results.map((item) => (
        <View
          key={item.questionId}
          style={[styles.answer, { borderLeftColor: item.isCorrect ? palette.success : palette.warning }]}
        >
          <AppText variant="bodySmall" tone="secondary">
            Question {item.position} · {item.isCorrect ? 'Correct' : 'Not correct'}
            {item.topicTitle ? ` · ${item.topicTitle}` : ''}
          </AppText>
          <AppText>{item.stem}</AppText>
          {!item.isCorrect ? (
            <AppText variant="bodySmall" tone="secondary">
              Your answer: {item.selectedAnswer ?? 'Not answered'}
            </AppText>
          ) : null}
          <AppText variant="bodySmall" tone="success">
            Correct answer: {item.correctAnswer}
          </AppText>
          <AppText variant="bodySmall" tone="secondary">
            {item.explanation}
          </AppText>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: spacing.lg,
  },
  answer: {
    gap: spacing.xs,
    padding: spacing.md,
    borderRadius: radius.md,
    borderLeftWidth: 4,
    backgroundColor: palette.surface,
  },
});
