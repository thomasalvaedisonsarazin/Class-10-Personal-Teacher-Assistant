import type {
  AnswerPhoto,
  ExamOverview,
  ModelPaper,
  PaperDocument,
  PaperScope,
  SubjectTest,
  SubjectTestResult,
} from '@/types/exam';
import type { QuizAnswer } from '@/types/quiz';

import { api } from './api';

/** Uploading several photos on a slow connection takes a while. */
const UPLOAD_TIMEOUT_MS = 180_000;
const START_TIMEOUT_MS = 60_000;

export const examService = {
  /** Plan status, recent subject tests and model papers of a subject. */
  async overview(subjectId: number): Promise<ExamOverview> {
    const { data } = await api.get<ExamOverview>(`/subjects/${subjectId}/exam-practice`);
    return data;
  },

  /** Starts (or resumes) a test across every topic passed in the subject. */
  async startSubjectTest(subjectId: number): Promise<SubjectTest> {
    const { data } = await api.post<SubjectTest>(`/subjects/${subjectId}/subject-tests`, undefined, {
      timeout: START_TIMEOUT_MS,
    });
    return data;
  },

  async submitSubjectTest(testId: number, answers: QuizAnswer[]): Promise<SubjectTestResult> {
    const { data } = await api.post<SubjectTestResult>(`/subject-tests/${testId}/submit`, { answers });
    return data;
  },

  /** Queues a model paper; it is written in the background (status "generating"). */
  async createPaper(subjectId: number, scope: PaperScope, chapterIds: number[]): Promise<ModelPaper> {
    const { data } = await api.post<ModelPaper>(`/subjects/${subjectId}/model-papers`, { scope, chapterIds });
    return data;
  },

  async getPaper(paperId: number): Promise<ModelPaper> {
    const { data } = await api.get<ModelPaper>(`/model-papers/${paperId}`);
    return data;
  },

  /** Printable HTML of the question paper or (after submitting) the answer key. */
  async document(paperId: number, kind: 'paper' | 'key'): Promise<PaperDocument> {
    const { data } = await api.get<PaperDocument>(`/model-papers/${paperId}/document`, { params: { kind } });
    return data;
  },

  /** Uploads the answer-sheet photos; marking starts and the answer key opens. */
  async submitAnswers(paperId: number, photos: AnswerPhoto[]): Promise<ModelPaper> {
    const form = new FormData();
    photos.forEach((photo) => {
      // React Native's FormData takes { uri, name, type } for files.
      form.append('photos', { uri: photo.uri, name: photo.fileName, type: photo.mimeType } as unknown as Blob);
    });
    const { data } = await api.post<ModelPaper>(`/model-papers/${paperId}/answers`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: UPLOAD_TIMEOUT_MS,
    });
    return data;
  },
};
