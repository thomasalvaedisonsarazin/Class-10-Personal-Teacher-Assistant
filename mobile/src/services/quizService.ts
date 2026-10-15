import type { QuizAnswer, QuizAttempt, QuizResult } from '@/types/quiz';

import { api } from './api';

/** Generating fresh questions can take a while the first time. */
const START_TIMEOUT_MS = 90_000;

export const quizService = {
  /** Starts (or resumes) a test with questions the student has never seen. */
  async startAttempt(topicId: number): Promise<QuizAttempt> {
    const { data } = await api.post<QuizAttempt>(`/topics/${topicId}/quiz-attempts`, undefined, {
      timeout: START_TIMEOUT_MS,
    });
    return data;
  },

  /** Server-side grading; >= passPct completes the topic. */
  async submitAttempt(attemptId: number, answers: QuizAnswer[]): Promise<QuizResult> {
    const { data } = await api.post<QuizResult>(`/quiz-attempts/${attemptId}/submit`, { answers });
    return data;
  },
};
