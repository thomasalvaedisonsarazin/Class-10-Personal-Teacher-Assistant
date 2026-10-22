import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Checkbox, HelperText } from 'react-native-paper';

import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { parseIdParam, useSubject } from '@/hooks/useCurriculum';
import { examKeys, useExamOverview } from '@/hooks/useExam';
import { durationLabel, paperStatusLabel, subjectTestBlocker } from '@/lib/exam';
import { getApiErrorMessage } from '@/services/api';
import { examService } from '@/services/examService';
import { MIN_TOUCH_TARGET, palette, radius, spacing } from '@/theme';
import type { PaperScope } from '@/types/exam';

export default function ExamPracticeScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { subjectId: raw } = useLocalSearchParams<{ subjectId: string }>();
  const subjectId = parseIdParam(raw);
  const subjectQuery = useSubject(subjectId);
  const overviewQuery = useExamOverview(subjectId);
  const [picking, setPicking] = useState(false);
  const [chapterIds, setChapterIds] = useState<number[]>([]);

  const create = useMutation({
    mutationFn: (scope: PaperScope) => examService.createPaper(subjectId, scope, scope === 'chapters' ? chapterIds : []),
    onSuccess: async (paper) => {
      setPicking(false);
      setChapterIds([]);
      await queryClient.invalidateQueries({ queryKey: examKeys.overview(subjectId) });
      router.push({ pathname: '/model-paper/[id]', params: { id: String(paper.id) } });
    },
  });

  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));
  const header = <AppHeader title="Exam practice" subtitle={subjectQuery.data?.name} onBack={goBack} />;

  if (overviewQuery.isPending) {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView />
      </Screen>
    );
  }
  if (overviewQuery.isError) {
    return (
      <Screen padded={false}>
        {header}
        <ErrorState
          message={getApiErrorMessage(overviewQuery.error)}
          onRetry={() => void overviewQuery.refetch()}
          retrying={overviewQuery.isFetching}
        />
      </Screen>
    );
  }

  const overview = overviewQuery.data;
  const blocker = subjectTestBlocker(overview);
  const canCreate = !overview.planRequired && overview.papersLeftToday > 0 && !create.isPending;
  const chapters = subjectQuery.data?.chapters ?? [];
  const toggleChapter = (id: number): void =>
    setChapterIds((current) => (current.includes(id) ? current.filter((c) => c !== id) : [...current, id]));

  return (
    <Screen padded={false} testID="exam-practice-screen">
      {header}
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={overviewQuery.isRefetching}
            onRefresh={() => void overviewQuery.refetch()}
            colors={[palette.primary]}
          />
        }
      >
        {overview.planRequired ? (
          <View style={[styles.card, styles.planCard]}>
            <MaterialCommunityIcons name="lock-outline" size={28} color={palette.onColor} />
            <AppText variant="subtitle" tone="inverse">
              Exam practice comes with a plan
            </AppText>
            <AppText variant="bodySmall" tone="inverse">
              Full-subject tests and board-pattern model papers with marks and answer keys are part of the
              monthly and yearly plans.
            </AppText>
            <PrimaryButton label="See plans" icon="star-outline" color={palette.surface} mode="outlined" onPress={() => router.push('/premium')} />
          </View>
        ) : null}

        <View style={styles.card}>
          <View style={styles.cardTitle}>
            <MaterialCommunityIcons name="format-list-checks" size={24} color={palette.primary} />
            <AppText variant="subtitle">Full-subject test</AppText>
          </View>
          <AppText variant="bodySmall" tone="secondary">
            Questions from every topic you have passed, mixed together. You see which topics to revise.
          </AppText>
          {blocker ? (
            <AppText variant="bodySmall" tone="warning">
              {blocker}
            </AppText>
          ) : (
            <PrimaryButton
              label="Start subject test"
              icon="play"
              onPress={() => router.push({ pathname: '/subject-test/[subjectId]', params: { subjectId: String(subjectId) } })}
              testID="start-subject-test"
            />
          )}
          {overview.recentTests.length > 0 ? (
            <AppText variant="caption" tone="secondary">
              Recent scores: {overview.recentTests.map((t) => `${Math.round(t.scorePct)}%`).join(' · ')}
            </AppText>
          ) : null}
        </View>

        <View style={styles.card}>
          <View style={styles.cardTitle}>
            <MaterialCommunityIcons name="file-document-edit-outline" size={24} color={palette.primary} />
            <AppText variant="subtitle">Model question papers</AppText>
          </View>
          <AppText variant="bodySmall" tone="secondary">
            Papers in the board exam pattern. Download the paper, write your answers on paper, then upload
            photos of your answer sheets. You get marks for every question, and then the answer key opens.
          </AppText>
          <PrimaryButton
            label={`Full syllabus · ${overview.fullPattern.totalMarks} marks · ${durationLabel(overview.fullPattern.durationMinutes)}`}
            icon="file-document-outline"
            onPress={() => create.mutate('full')}
            disabled={!canCreate}
            loading={create.isPending && create.variables === 'full'}
            testID="create-full-paper"
          />
          <PrimaryButton
            label={`Chosen chapters · ${overview.unitPattern.totalMarks} marks · ${durationLabel(overview.unitPattern.durationMinutes)}`}
            icon="book-open-page-variant-outline"
            mode="outlined"
            onPress={() => setPicking((p) => !p)}
            disabled={!canCreate}
            testID="pick-chapters"
          />
          {picking ? (
            <View style={styles.chapters}>
              {chapters.map((chapter) => (
                <Checkbox.Item
                  key={chapter.id}
                  label={chapter.title}
                  status={chapterIds.includes(chapter.id) ? 'checked' : 'unchecked'}
                  onPress={() => toggleChapter(chapter.id)}
                  color={palette.primary}
                  style={styles.chapterItem}
                />
              ))}
              <PrimaryButton
                label={`Create paper (${chapterIds.length} chapter${chapterIds.length === 1 ? '' : 's'})`}
                icon="check"
                onPress={() => create.mutate('chapters')}
                disabled={!canCreate || chapterIds.length === 0}
                loading={create.isPending && create.variables === 'chapters'}
              />
            </View>
          ) : null}
          {!overview.planRequired ? (
            <AppText variant="caption" tone="secondary">
              {overview.papersLeftToday > 0
                ? `You can create ${overview.papersLeftToday} more paper${overview.papersLeftToday === 1 ? '' : 's'} today.`
                : 'You have created today’s papers. Come back tomorrow for more.'}
            </AppText>
          ) : null}
          {create.isError ? (
            <HelperText type="error" visible>
              {getApiErrorMessage(create.error)}
            </HelperText>
          ) : null}
        </View>

        {overview.papers.length > 0 ? (
          <View style={styles.card}>
            <AppText variant="subtitle">Your papers</AppText>
            {overview.papers.map((paper) => (
              <Pressable
                key={paper.id}
                accessibilityRole="button"
                onPress={() => router.push({ pathname: '/model-paper/[id]', params: { id: String(paper.id) } })}
                style={({ pressed }) => [styles.paperRow, pressed && styles.pressed]}
                testID={`paper-${paper.id}`}
              >
                <View style={styles.paperText}>
                  <AppText>{paper.title}</AppText>
                  <AppText variant="caption" tone="secondary">
                    {new Date(paper.createdAt).toLocaleDateString()} · {paperStatusLabel(paper)}
                  </AppText>
                </View>
                <MaterialCommunityIcons name="chevron-right" size={24} color={palette.textSecondary} />
              </Pressable>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  card: {
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: palette.surface,
  },
  planCard: {
    backgroundColor: palette.primary,
  },
  cardTitle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  chapters: {
    gap: spacing.xs,
  },
  chapterItem: {
    borderRadius: radius.md,
    backgroundColor: palette.surfaceMuted,
  },
  paperRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: MIN_TOUCH_TARGET,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: palette.outline,
  },
  paperText: {
    flex: 1,
    gap: spacing.xxs,
  },
  pressed: {
    opacity: 0.7,
  },
});
