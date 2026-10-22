import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { HelperText } from 'react-native-paper';

import { AnswerPhotos } from '@/components/exam/AnswerPhotos';
import { PaperView } from '@/components/exam/PaperView';
import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { parseIdParam } from '@/hooks/useCurriculum';
import { examKeys, useModelPaper } from '@/hooks/useExam';
import { canUploadAnswers, durationLabel, formatMarks, isSubmitted } from '@/lib/exam';
import { printPaper, sharePaperPdf } from '@/lib/paperPdf';
import { getApiErrorMessage } from '@/services/api';
import { examService } from '@/services/examService';
import { palette, radius, spacing } from '@/theme';
import type { AnswerPhoto, ModelPaper } from '@/types/exam';

type DocKind = 'paper' | 'key';

export default function ModelPaperScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { id } = useLocalSearchParams<{ id: string }>();
  const paperId = parseIdParam(id);
  const paperQuery = useModelPaper(paperId);
  const [photos, setPhotos] = useState<AnswerPhoto[]>([]);
  const [showPaper, setShowPaper] = useState(false);

  const download = useMutation({
    mutationFn: async ({ kind, print }: { kind: DocKind; print: boolean }) => {
      const doc = await examService.document(paperId, kind);
      await (print ? printPaper(doc) : sharePaperPdf(doc));
    },
  });

  const submit = useMutation({
    mutationFn: () => examService.submitAnswers(paperId, photos),
    onSuccess: async (paper: ModelPaper) => {
      setPhotos([]);
      queryClient.setQueryData(examKeys.paper(paperId), paper);
      await queryClient.invalidateQueries({ queryKey: examKeys.overview(paper.subjectId) });
    },
  });

  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));
  const header = <AppHeader title="Model paper" subtitle={paperQuery.data?.title} onBack={goBack} />;

  if (paperQuery.isPending) {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView />
      </Screen>
    );
  }
  if (paperQuery.isError) {
    return (
      <Screen padded={false}>
        {header}
        <ErrorState
          message={getApiErrorMessage(paperQuery.error)}
          onRetry={() => void paperQuery.refetch()}
          retrying={paperQuery.isFetching}
        />
      </Screen>
    );
  }

  const paper = paperQuery.data;

  if (paper.status === 'generating') {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView message="Writing your paper in the board exam pattern. This takes 1–3 minutes — you can leave and come back." />
      </Screen>
    );
  }
  if (paper.status === 'generation_failed') {
    return (
      <Screen padded={false}>
        {header}
        <ErrorState
          title="This paper could not be written"
          message="Please go back and create a new paper."
          onRetry={goBack}
          retryLabel="Go back"
        />
      </Screen>
    );
  }

  const submitted = isSubmitted(paper.status);
  const downloadButtons = (kind: DocKind) => (
    <View style={styles.row}>
      <PrimaryButton
        label={kind === 'paper' ? 'Download paper' : 'Download answer key'}
        icon="file-pdf-box"
        fullWidth={false}
        style={styles.flex}
        onPress={() => download.mutate({ kind, print: false })}
        loading={download.isPending && download.variables?.kind === kind && !download.variables.print}
        testID={`download-${kind}`}
      />
      <PrimaryButton
        label="Print"
        icon="printer"
        mode="outlined"
        fullWidth={false}
        onPress={() => download.mutate({ kind, print: true })}
        disabled={download.isPending}
      />
    </View>
  );

  return (
    <Screen padded={false} testID="model-paper-screen">
      {header}
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={paperQuery.isRefetching}
            onRefresh={() => void paperQuery.refetch()}
            colors={[palette.primary]}
          />
        }
      >
        <View style={styles.meta}>
          <AppText variant="caption" tone="secondary">
            {paper.totalMarks} marks · {durationLabel(paper.durationMinutes)}
          </AppText>
        </View>

        {paper.status === 'graded' ? (
          <View style={[styles.card, styles.scoreCard]}>
            <MaterialCommunityIcons name="clipboard-check-outline" size={36} color={palette.onColor} />
            <AppText variant="display" tone="inverse">
              {formatMarks(paper.score ?? 0)} / {paper.totalMarks}
            </AppText>
            <View style={styles.partScores}>
              {(paper.partScores ?? []).map((p) => (
                <AppText key={p.label} variant="bodySmall" tone="inverse">
                  Part {p.label}: {formatMarks(p.scored)}/{p.total}
                </AppText>
              ))}
            </View>
            {paper.feedback ? (
              <AppText variant="bodySmall" tone="inverse" center>
                {paper.feedback}
              </AppText>
            ) : null}
          </View>
        ) : null}

        {paper.status === 'grading' ? (
          <View style={styles.card}>
            <LoadingView
              fullScreen={false}
              message="Marking your answers. This takes a few minutes — the answer key is ready below."
            />
          </View>
        ) : null}

        {paper.status === 'grading_failed' && paper.feedback ? (
          <View style={[styles.card, styles.warnCard]}>
            <AppText tone="inverse">{paper.feedback}</AppText>
          </View>
        ) : null}

        {!submitted ? (
          <View style={styles.card}>
            <AppText variant="subtitle">1. Get the question paper</AppText>
            <AppText variant="bodySmall" tone="secondary">
              Save it as a PDF or print it. You can also read it here.
            </AppText>
            {downloadButtons('paper')}
            <PrimaryButton
              label={showPaper ? 'Hide questions' : 'Show questions here'}
              mode="text"
              onPress={() => setShowPaper((s) => !s)}
            />
            {showPaper ? <PaperView parts={paper.parts} /> : null}
          </View>
        ) : null}

        {!submitted ? (
          <View style={styles.card}>
            <AppText variant="subtitle">2. Write your answers on paper</AppText>
            <AppText variant="bodySmall" tone="secondary">
              Give yourself {durationLabel(paper.durationMinutes)}, like the real exam. Write the question number
              clearly before every answer.
            </AppText>
          </View>
        ) : null}

        {canUploadAnswers(paper.status) ? (
          <View style={styles.card}>
            <AppText variant="subtitle">
              {paper.status === 'grading_failed' ? 'Upload your answer photos again' : '3. Upload photos of your answers'}
            </AppText>
            <AppText variant="bodySmall" tone="secondary">
              Take a clear, bright photo of every page, in order. After you submit, your answers are marked and the
              answer key opens. Photos are deleted after marking.
            </AppText>
            <AnswerPhotos photos={photos} onChange={setPhotos} disabled={submit.isPending} />
            <PrimaryButton
              label="Submit answers for marking"
              icon="send"
              onPress={() => submit.mutate()}
              disabled={photos.length === 0}
              loading={submit.isPending}
              testID="submit-answers"
            />
            {submit.isError ? (
              <HelperText type="error" visible>
                {getApiErrorMessage(submit.error)}
              </HelperText>
            ) : null}
          </View>
        ) : null}

        {submitted && paper.answerKey ? (
          <View style={styles.card}>
            <AppText variant="subtitle">Answer key and suggested answers</AppText>
            {downloadButtons('key')}
            <PaperView parts={paper.parts} answerKey={paper.answerKey} />
          </View>
        ) : null}

        {download.isError ? (
          <HelperText type="error" visible>
            {getApiErrorMessage(download.error)}
          </HelperText>
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
  meta: {
    alignItems: 'center',
  },
  card: {
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: palette.surface,
  },
  scoreCard: {
    alignItems: 'center',
    backgroundColor: palette.success,
  },
  warnCard: {
    backgroundColor: palette.warning,
  },
  partScores: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: spacing.md,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  flex: {
    flex: 1,
  },
});
