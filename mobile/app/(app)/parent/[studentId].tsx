import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';

import { AppHeader } from '@/components/layout/AppHeader';
import { ProgressBar } from '@/components/parent/ProgressBar';
import { AppText, ErrorState, LoadingView, Screen } from '@/components/ui';
import { parseIdParam } from '@/hooks/useCurriculum';
import { relativeDay } from '@/lib/time';
import { getApiErrorMessage } from '@/services/api';
import { parentService } from '@/services/parentService';
import { palette, radius, safeTileColor, spacing } from '@/theme';
import type { TopicStatus } from '@/types/curriculum';

const STATUS_ICON: Record<TopicStatus, { icon: 'check-circle' | 'play-circle' | 'circle-outline' | 'lock'; color: string }> = {
  completed: { icon: 'check-circle', color: palette.success },
  active: { icon: 'play-circle', color: palette.primary },
  available: { icon: 'circle-outline', color: palette.primary },
  locked: { icon: 'lock', color: palette.locked },
};

interface StatProps {
  label: string;
  value: string;
}

function Stat({ label, value }: StatProps) {
  return (
    <View style={styles.stat}>
      <AppText variant="title">{value}</AppText>
      <AppText variant="caption" tone="secondary" center>
        {label}
      </AppText>
    </View>
  );
}

/** Read-only report for one linked child. */
export default function ChildReportScreen() {
  const router = useRouter();
  const { studentId } = useLocalSearchParams<{ studentId: string }>();
  const id = parseIdParam(studentId);
  const report = useQuery({
    queryKey: ['parent', 'child', id],
    queryFn: () => parentService.childReport(id),
    enabled: Number.isInteger(id) && id > 0,
  });
  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/parent'));

  if (report.isPending) {
    return (
      <Screen padded={false}>
        <AppHeader title="Report" onBack={goBack} />
        <LoadingView />
      </Screen>
    );
  }
  if (report.isError) {
    return (
      <Screen padded={false}>
        <AppHeader title="Report" onBack={goBack} />
        <ErrorState message={getApiErrorMessage(report.error)} onRetry={() => void report.refetch()} />
      </Screen>
    );
  }

  const r = report.data;
  return (
    <Screen padded={false} testID="child-report">
      <AppHeader title={r.name ?? 'Your child'} subtitle={`Active ${relativeDay(r.lastActiveAt)}`} onBack={goBack} />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={[styles.card, styles.statsRow]}>
          <Stat label="topics passed" value={`${r.topicsCompleted}/${r.topicsTotal}`} />
          <Stat label="minutes learning (7 days)" value={String(r.minutesLearningThisWeek)} />
          <Stat
            label="average test (7 days)"
            value={r.averageScoreThisWeek !== null ? `${Math.round(r.averageScoreThisWeek)}%` : '—'}
          />
        </View>
        {r.reExplanationsThisWeek > 0 ? (
          <AppText variant="bodySmall" tone="secondary">
            Asked for a new explanation {r.reExplanationsThisWeek} time(s) this week — a good sign of
            trying to understand.
          </AppText>
        ) : null}

        <AppText variant="subtitle">Subjects</AppText>
        {r.subjectsDetail.map((subject, i) => {
          const color = safeTileColor(subject.tileColor, i);
          return (
            <View key={subject.subjectId} style={[styles.card, { borderLeftColor: color }, styles.subjectCard]}>
              <View style={styles.rowBetween}>
                <AppText variant="subtitle">{subject.name}</AppText>
                <AppText tone="secondary">
                  {subject.completed}/{subject.total}
                </AppText>
              </View>
              <ProgressBar value={subject.completed} total={subject.total} color={color} />
              {subject.topics.map((topic) => {
                const ui = STATUS_ICON[topic.status];
                return (
                  <View key={topic.title} style={styles.topicRow}>
                    <MaterialCommunityIcons name={ui.icon} size={20} color={ui.color} />
                    <AppText
                      variant="bodySmall"
                      tone={topic.status === 'locked' ? 'secondary' : 'primary'}
                      style={styles.topicTitle}
                    >
                      {topic.title}
                    </AppText>
                    {topic.bestScorePct !== null ? (
                      <AppText variant="caption" tone="secondary">
                        {Math.round(topic.bestScorePct)}%
                      </AppText>
                    ) : null}
                  </View>
                );
              })}
            </View>
          );
        })}

        <AppText variant="subtitle">Recent tests</AppText>
        {r.recentTests.length === 0 ? (
          <AppText tone="secondary">No tests yet.</AppText>
        ) : (
          r.recentTests.map((test) => (
            <View key={`${test.submittedAt}-${test.topicTitle}`} style={[styles.card, styles.rowBetween]}>
              <View style={styles.topicTitle}>
                <AppText variant="bodySmall">{test.topicTitle}</AppText>
                <AppText variant="caption" tone="secondary">
                  {test.subjectName} · {relativeDay(test.submittedAt)}
                </AppText>
              </View>
              <AppText tone={test.passed ? 'success' : 'warning'}>
                {Math.round(test.scorePct)}% {test.passed ? 'passed' : 'retry'}
              </AppText>
            </View>
          ))
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  card: {
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: palette.surface,
  },
  subjectCard: {
    borderLeftWidth: 5,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stat: {
    flex: 1,
    alignItems: 'center',
    gap: spacing.xxs,
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md,
  },
  topicRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  topicTitle: {
    flex: 1,
  },
});
