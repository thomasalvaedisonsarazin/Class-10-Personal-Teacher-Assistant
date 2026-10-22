import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { StyleSheet, View } from 'react-native';

import { AnswerReview } from '@/components/quiz/AnswerReview';
import { AppText, PrimaryButton } from '@/components/ui';
import { palette, radius, spacing } from '@/theme';
import type { SubjectTestResult } from '@/types/exam';

/** Score at or above this is shown as a good result. */
const GOOD_PCT = 60;

export interface SubjectTestResultViewProps {
  result: SubjectTestResult;
  onReviseTopic: (topicId: number) => void;
  onRetry: () => void;
  onDone: () => void;
}

/** Score of a full-subject test, the topics to revise, and every answer. */
export function SubjectTestResultView({ result, onReviseTopic, onRetry, onDone }: SubjectTestResultViewProps) {
  const good = result.scorePct >= GOOD_PCT;

  return (
    <View style={styles.container} testID="subject-test-result">
      <View style={[styles.scoreCard, { backgroundColor: good ? palette.success : palette.warning }]}>
        <MaterialCommunityIcons name={good ? 'trophy-outline' : 'book-refresh-outline'} size={40} color={palette.onColor} />
        <AppText variant="display" tone="inverse">
          {Math.round(result.scorePct)}%
        </AppText>
        <AppText tone="inverse" center>
          {result.correctCount} of {result.total} correct across the subject
        </AppText>
      </View>

      {result.weakTopics.length > 0 ? (
        <View style={styles.section}>
          <AppText variant="subtitle">Revise these topics</AppText>
          {result.weakTopics.map((topic) => (
            <View key={topic.topicId} style={styles.weak}>
              <View style={styles.weakText}>
                <AppText>{topic.title}</AppText>
                <AppText variant="caption" tone="secondary">
                  {topic.correct} of {topic.total} correct
                </AppText>
              </View>
              <PrimaryButton
                label="Revise"
                mode="outlined"
                fullWidth={false}
                onPress={() => onReviseTopic(topic.topicId)}
              />
            </View>
          ))}
        </View>
      ) : (
        <AppText tone="success" center>
          Great — every topic in this test went well!
        </AppText>
      )}

      <View style={styles.section}>
        <PrimaryButton label="Take another subject test" icon="refresh" onPress={onRetry} />
        <PrimaryButton label="Back to exam practice" mode="text" onPress={onDone} />
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
  section: {
    gap: spacing.md,
  },
  weak: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: palette.surface,
  },
  weakText: {
    flex: 1,
    gap: spacing.xxs,
  },
});
