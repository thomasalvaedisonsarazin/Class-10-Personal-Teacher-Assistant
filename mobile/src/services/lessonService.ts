import type { LessonLanguage } from '@/types/api';
import type { GenerationJob, LessonResponse, LessonStyle } from '@/types/lessons';

import { api } from './api';

export const lessonService = {
  /** The lesson to play for a topic (may start generating the first explanation). */
  async openLesson(topicId: number): Promise<LessonResponse> {
    const { data } = await api.get<LessonResponse>(`/topics/${topicId}/lesson`);
    return data;
  },

  /** Ask for a new explanation in a different style. Rejects with 429 `generation_limit`. */
  async notClear(topicId: number, lessonId: number | null): Promise<LessonResponse> {
    const { data } = await api.post<LessonResponse>(`/topics/${topicId}/not-clear`, { lessonId });
    return data;
  },

  /** Explain in the style the student picked (cached, or generated now). */
  async chooseStyle(topicId: number, style: LessonStyle): Promise<LessonResponse> {
    const { data } = await api.post<LessonResponse>(`/topics/${topicId}/lesson-style`, { style });
    return data;
  },

  /** Explain in English, Tamil or Tanglish; the server remembers the choice. */
  async chooseLanguage(
    topicId: number,
    language: LessonLanguage,
    style: LessonStyle | null,
  ): Promise<LessonResponse> {
    const { data } = await api.post<LessonResponse>(`/topics/${topicId}/lesson-language`, {
      language,
      style,
    });
    return data;
  },

  async markClear(topicId: number, lessonId: number): Promise<void> {
    await api.post(`/topics/${topicId}/clear`, { lessonId });
  },

  async getJob(jobId: number): Promise<GenerationJob> {
    const { data } = await api.get<GenerationJob>(`/jobs/${jobId}`);
    return data;
  },

  async saveProgress(lessonId: number, watchedSec: number, completed: boolean): Promise<void> {
    await api.put(`/lessons/${lessonId}/progress`, { watchedSec: Math.floor(watchedSec), completed });
  },
};
