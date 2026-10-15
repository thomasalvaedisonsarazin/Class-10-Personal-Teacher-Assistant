import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { lessonService } from '@/services/lessonService';
import type { LessonLanguage } from '@/types/api';
import type { GenerationJob, Lesson, LessonResponse, LessonStyle } from '@/types/lessons';

const POLL_INTERVAL_MS = 3000;

export interface LessonFlow {
  lesson: Lesson | null;
  /** Job being generated (null when a lesson is ready). */
  job: GenerationJob | null;
  /** Friendly error when generation failed. */
  failedMessage: string | null;
  isLoading: boolean;
  loadError: unknown;
  reload: () => void;
  notClear: () => void;
  notClearPending: boolean;
  notClearError: unknown;
  chooseStyle: (style: LessonStyle) => void;
  chooseStylePending: boolean;
  chooseLanguage: (language: LessonLanguage) => void;
}

function isFinished(job: GenerationJob): boolean {
  return job.lesson !== null || job.status === 'failed' || job.status === 'done';
}

/**
 * Lesson state for a topic: opens the lesson, polls a generation job until the
 * audio is ready, and swaps in a new explanation when the student taps "Not clear".
 */
export function useLessonFlow(topicId: number, onLanguageChanged?: () => void): LessonFlow {
  const queryClient = useQueryClient();
  const [override, setOverride] = useState<LessonResponse | null>(null);

  const opened = useQuery({
    queryKey: ['lesson', topicId],
    queryFn: () => lessonService.openLesson(topicId),
    enabled: Number.isInteger(topicId) && topicId > 0,
    staleTime: 0,
  });

  const response = override ?? opened.data ?? null;
  const initialJob = response?.job ?? null;
  const pollJobId = initialJob && !isFinished(initialJob) ? initialJob.id : null;

  const jobQuery = useQuery({
    queryKey: ['jobs', pollJobId],
    queryFn: () => lessonService.getJob(pollJobId ?? 0),
    enabled: pollJobId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && isFinished(data) ? false : POLL_INTERVAL_MS;
    },
  });

  const job = (pollJobId !== null ? jobQuery.data : null) ?? initialJob;
  const lesson = response?.lesson ?? job?.lesson ?? null;
  const failedMessage =
    !lesson && job?.status === 'failed'
      ? (job.error ?? 'We could not prepare this explanation. Please try again.')
      : null;

  const notClearMutation = useMutation({
    mutationFn: () => lessonService.notClear(topicId, lesson?.id ?? null),
    onSuccess: (data) => setOverride(data),
  });

  const chooseStyleMutation = useMutation({
    mutationFn: (style: LessonStyle) => lessonService.chooseStyle(topicId, style),
    onSuccess: (data) => setOverride(data),
  });

  const chooseLanguageMutation = useMutation({
    mutationFn: (language: LessonLanguage) =>
      lessonService.chooseLanguage(topicId, language, lesson?.style ?? null),
    onSuccess: (data) => {
      setOverride(data);
      onLanguageChanged?.();
    },
  });

  return {
    lesson,
    job: lesson ? null : job,
    failedMessage,
    isLoading: opened.isPending && override === null,
    loadError: override === null ? opened.error : null,
    reload: () => {
      setOverride(null);
      void queryClient.invalidateQueries({ queryKey: ['lesson', topicId] });
    },
    notClear: () => notClearMutation.mutate(),
    notClearPending: notClearMutation.isPending,
    notClearError: notClearMutation.error ?? chooseStyleMutation.error ?? chooseLanguageMutation.error,
    chooseStyle: (style) => chooseStyleMutation.mutate(style),
    chooseStylePending: chooseStyleMutation.isPending || chooseLanguageMutation.isPending,
    chooseLanguage: (language) => chooseLanguageMutation.mutate(language),
  };
}
