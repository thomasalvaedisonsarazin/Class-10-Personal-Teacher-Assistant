import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { curriculumService } from '@/services/curriculumService';

export const curriculumKeys = {
  subjects: ['subjects'] as const,
  subject: (id: number) => ['subjects', id] as const,
  topic: (id: number) => ['topics', id] as const,
};

export function useStreak() {
  return useQuery({ queryKey: ['streak'], queryFn: curriculumService.getStreak, staleTime: 60_000 });
}

export function useSubjects() {
  return useQuery({ queryKey: curriculumKeys.subjects, queryFn: curriculumService.getSubjects });
}

export function useSubject(subjectId: number) {
  return useQuery({
    queryKey: curriculumKeys.subject(subjectId),
    queryFn: () => curriculumService.getSubject(subjectId),
    enabled: Number.isInteger(subjectId) && subjectId > 0,
  });
}

export function useTopic(topicId: number) {
  return useQuery({
    queryKey: curriculumKeys.topic(topicId),
    queryFn: () => curriculumService.getTopic(topicId),
    enabled: Number.isInteger(topicId) && topicId > 0,
  });
}

/** Starting a topic changes tiles and topic lists, so refresh them afterwards. */
export function useStartTopic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: curriculumService.startTopic,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: curriculumKeys.subjects }),
        queryClient.invalidateQueries({ queryKey: ['topics'] }),
      ]);
    },
  });
}

/** Parses an expo-router `[id]` param. Returns NaN for anything invalid. */
export function parseIdParam(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw && /^\d+$/.test(raw) ? Number(raw) : Number.NaN;
}
