import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui';
import { formatMarks } from '@/lib/exam';
import { palette, radius, spacing } from '@/theme';
import type { AnswerKeyItem, PaperPart } from '@/types/exam';

const LETTERS = 'abcd';

export interface PaperViewProps {
  parts: PaperPart[];
  /** Shown only after the answers were submitted. */
  answerKey?: AnswerKeyItem[] | null;
}

function partNote(part: PaperPart): string {
  const notes = [part.answer < part.printed ? `Answer any ${part.answer}.` : 'Answer all.'];
  if (part.eitherOr) notes.push('Either (a) or (b) in each.');
  const compulsory = part.questions.find((q) => q.compulsory);
  if (compulsory) notes.push(`Question ${compulsory.number} is compulsory.`);
  return notes.join(' ');
}

/** The paper on screen; with ``answerKey`` it also shows the suggested answers and marks. */
export function PaperView({ parts, answerKey }: PaperViewProps) {
  const keys = new Map((answerKey ?? []).map((k) => [k.number, k]));

  return (
    <View style={styles.container}>
      {parts.map((part) => (
        <View key={part.label} style={styles.part}>
          <View style={styles.partHead}>
            <AppText variant="subtitle">Part {part.label}</AppText>
            <AppText variant="caption" tone="secondary">
              {part.answer} × {part.marks} = {part.answer * part.marks} marks
            </AppText>
          </View>
          <AppText variant="caption" tone="secondary">
            {partNote(part)}
          </AppText>
          {part.questions.map((q) => {
            const key = keys.get(q.number);
            return (
              <View key={q.number} style={styles.question}>
                <AppText>
                  <AppText variant="label">{q.number}. </AppText>
                  {q.altText ? `(a) ${q.text}` : q.text}
                </AppText>
                {q.options.map((option, i) => (
                  <AppText key={option} variant="bodySmall" style={styles.option}>
                    ({LETTERS[i] ?? i + 1}) {option}
                  </AppText>
                ))}
                {q.altText ? (
                  <>
                    <AppText variant="label" center>
                      (OR)
                    </AppText>
                    <AppText>(b) {q.altText}</AppText>
                  </>
                ) : null}
                {key ? <KeyBlock item={key} eitherOr={Boolean(q.altText)} /> : null}
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}

function KeyBlock({ item, eitherOr }: { item: AnswerKeyItem; eitherOr: boolean }) {
  const marked = item.marksAwarded !== null;
  return (
    <View style={styles.key}>
      {marked ? (
        <AppText variant="label" tone={item.attempted ? 'success' : 'warning'}>
          {item.attempted ? `Your marks: ${formatMarks(item.marksAwarded ?? 0)} / ${item.maxMarks}` : 'Not attempted'}
        </AppText>
      ) : null}
      {item.feedback ? (
        <AppText variant="bodySmall" tone="secondary">
          {item.feedback}
        </AppText>
      ) : null}
      <AppText variant="bodySmall">
        <AppText variant="label">{eitherOr ? 'Answer (a): ' : 'Answer: '}</AppText>
        {item.answer}
      </AppText>
      {item.points.map((p) => (
        <AppText key={p} variant="caption" tone="secondary">
          • {p}
        </AppText>
      ))}
      {eitherOr && item.altAnswer ? (
        <>
          <AppText variant="bodySmall">
            <AppText variant="label">Answer (b): </AppText>
            {item.altAnswer}
          </AppText>
          {item.altPoints.map((p) => (
            <AppText key={p} variant="caption" tone="secondary">
              • {p}
            </AppText>
          ))}
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.xl,
  },
  part: {
    gap: spacing.md,
  },
  partHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    borderBottomWidth: 1,
    borderBottomColor: palette.outline,
    paddingBottom: spacing.xs,
  },
  question: {
    gap: spacing.xs,
  },
  option: {
    paddingLeft: spacing.lg,
  },
  key: {
    gap: spacing.xs,
    marginTop: spacing.xs,
    padding: spacing.md,
    borderRadius: radius.md,
    borderLeftWidth: 4,
    borderLeftColor: palette.success,
    backgroundColor: palette.surfaceMuted,
  },
});
