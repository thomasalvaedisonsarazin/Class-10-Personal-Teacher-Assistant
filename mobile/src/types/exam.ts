/** Exam practice: full-subject tests and model question papers (plan holders). */

import type { QuestionResult, QuizQuestion } from './quiz';

export interface SubjectTest {
  testId: number;
  subjectId: number;
  expiresAt: string;
  questions: QuizQuestion[];
}

export interface SubjectTestQuestionResult extends QuestionResult {
  topicId: number;
  topicTitle: string;
}

export interface TopicScore {
  topicId: number;
  title: string;
  correct: number;
  total: number;
}

export interface SubjectTestResult {
  testId: number;
  subjectId: number;
  scorePct: number;
  correctCount: number;
  total: number;
  results: SubjectTestQuestionResult[];
  weakTopics: TopicScore[];
}

export interface SubjectTestSummary {
  id: number;
  scorePct: number;
  correctCount: number;
  total: number;
  submittedAt: string;
}

export type PaperScope = 'full' | 'chapters';

export type PaperStatus =
  | 'generating'
  | 'ready'
  | 'grading'
  | 'graded'
  | 'generation_failed'
  | 'grading_failed';

export interface ModelPaperSummary {
  id: number;
  subjectId: number;
  title: string;
  scope: PaperScope;
  chapterIds: number[];
  status: PaperStatus;
  totalMarks: number;
  durationMinutes: number;
  score: number | null;
  createdAt: string;
}

export interface PaperQuestion {
  number: number;
  text: string;
  options: string[];
  altText: string | null;
  compulsory: boolean;
}

export interface PaperPart {
  label: string;
  kind: string;
  marks: number;
  printed: number;
  answer: number;
  eitherOr: boolean;
  questions: PaperQuestion[];
}

export interface AnswerKeyItem {
  number: number;
  maxMarks: number;
  answer: string;
  points: string[];
  altAnswer: string | null;
  altPoints: string[];
  attempted: boolean | null;
  marksAwarded: number | null;
  feedback: string | null;
}

export interface PartScore {
  label: string;
  scored: number;
  total: number;
}

export interface ModelPaper extends ModelPaperSummary {
  parts: PaperPart[];
  /** Only after the student has submitted photos of their answers. */
  answerKey: AnswerKeyItem[] | null;
  partScores: PartScore[] | null;
  feedback: string | null;
  photosSubmitted: number;
}

export interface PaperDocument {
  html: string;
  fileName: string;
}

export interface PatternInfo {
  totalMarks: number;
  durationMinutes: number;
}

export interface ExamOverview {
  subjectId: number;
  planRequired: boolean;
  completedTopics: number;
  minTopics: number;
  recentTests: SubjectTestSummary[];
  papers: ModelPaperSummary[];
  papersLeftToday: number;
  fullPattern: PatternInfo;
  unitPattern: PatternInfo;
}

/** A photo of an answer sheet picked on the phone, waiting to be uploaded. */
export interface AnswerPhoto {
  uri: string;
  mimeType: string;
  fileName: string;
}
