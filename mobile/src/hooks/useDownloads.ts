import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  deleteDownload,
  downloadLesson,
  getDownload,
  listDownloads,
  offlineSupported,
} from '@/services/offlineService';
import type { Lesson } from '@/types/lessons';

export const downloadKeys = {
  all: ['downloads'] as const,
  one: (lessonId: number) => ['downloads', lessonId] as const,
};

export function useDownloads() {
  return useQuery({ queryKey: downloadKeys.all, queryFn: listDownloads, enabled: offlineSupported });
}

export function useDownload(lessonId: number | null) {
  return useQuery({
    queryKey: downloadKeys.one(lessonId ?? 0),
    queryFn: () => getDownload(lessonId ?? 0),
    enabled: offlineSupported && lessonId !== null,
  });
}

export interface DownloadInput {
  lesson: Lesson;
  topicTitle: string;
  subjectName: string;
}

export function useDownloadLesson() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lesson, topicTitle, subjectName }: DownloadInput) =>
      downloadLesson(lesson, topicTitle, subjectName),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: downloadKeys.all }),
  });
}

export function useDeleteDownload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (lessonId: number) => deleteDownload(lessonId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: downloadKeys.all }),
  });
}
