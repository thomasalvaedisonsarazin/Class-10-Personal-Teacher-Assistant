/** Admin API types (camelCase JSON). */
import type { Medium, Page, UserRole } from './api';

export type LessonStyle =
  | 'base'
  | 'analogy'
  | 'step_by_step'
  | 'story'
  | 'real_life'
  | 'worked_example'
  | 'visual';
export type LessonLanguage = 'en' | 'ta' | 'tanglish';
export type LessonStatus = 'pending' | 'generating' | 'audio_ready' | 'ready' | 'failed';
export type QuestionType = 'mcq' | 'true_false' | 'fill_blank';

export interface AdminStats {
  students: number;
  activeStudentsWeek: number;
  subjects: number;
  topicsPublished: number;
  lessonsReady: number;
  lessonsFlagged: number;
  questionsApproved: number;
  questionsFlagged: number;
  quizAttemptsWeek: number;
  passRateWeek: number | null;
  generationsToday: number;
  failedJobsWeek: number;
}

/** One class of a board (e.g. TN State Board Class 11); hidden classes are not shown to students. */
export interface AdminBoard {
  id: number;
  code: string;
  name: string;
  isActive: boolean;
  family: string;
  grade: number;
  chooseSubjects: boolean;
}

export interface AdminTopic {
  id: number;
  title: string;
  titleTa: string | null;
  learningObjectives: string;
  learningObjectivesTa: string | null;
  displayOrder: number;
  isPublished: boolean;
  lessonCount: number;
  questionCount: number;
}

export interface AdminChapter {
  id: number;
  title: string;
  titleTa: string | null;
  displayOrder: number;
  topics: AdminTopic[];
}

export interface AdminSubject {
  id: number;
  name: string;
  nameTa: string | null;
  tileColor: string;
  icon: string;
  displayOrder: number;
  /** Language subject always shown in this language ("ta" = Tamil). */
  fixedMedium?: Medium | null;
  chapters: AdminChapter[];
}

export interface CurriculumTree {
  board: AdminBoard;
  subjects: AdminSubject[];
}

export interface TopicInput {
  title?: string;
  titleTa?: string;
  learningObjectives?: string;
  learningObjectivesTa?: string;
  isPublished?: boolean;
}

export interface ImportResult {
  created: Record<string, number>;
  updated: Record<string, number>;
}

export interface AdminLesson {
  id: number;
  topicId: number;
  topicTitle: string;
  medium: Medium;
  language: LessonLanguage;
  style: LessonStyle;
  source: 'uploaded' | 'ai_generated';
  title: string | null;
  status: LessonStatus;
  isFlagged: boolean;
  durationSec: number | null;
  audioUrl: string | null;
  videoUrl: string | null;
  createdAt: string;
}

export interface AdminQuestion {
  id: number;
  topicId: number;
  medium: Medium;
  type: QuestionType;
  stem: string;
  options: string[] | null;
  correctAnswer: string;
  explanation: string;
  difficulty: number;
  source: 'ai' | 'admin';
  isApproved: boolean;
  isFlagged: boolean;
  createdAt: string;
}

export interface QuestionInput {
  topicId: number;
  medium: Medium;
  type: 'mcq' | 'true_false';
  stem: string;
  options: string[];
  correctAnswer: string;
  explanation: string;
  difficulty: number;
}

export interface AdminUser {
  id: number;
  email: string;
  fullName: string | null;
  role: UserRole;
  medium: Medium | null;
  isActive: boolean;
  createdAt: string;
  /** Student's class (board) and, for 11th / 12th, their six subjects. */
  boardId?: number | null;
  subjectIds?: number[];
}

/** Changes an admin may make to a user (class / subjects even after payment). */
export interface AdminUserUpdate {
  role?: UserRole;
  isActive?: boolean;
  boardId?: number;
  subjectIds?: number[];
}

export type AdminPage<T> = Page<T>;

/** School / teacher referral partner (amounts in rupees). */
export interface AdminPartner {
  id: number;
  name: string;
  email: string;
  code: string;
  shareLink: string;
  commissionPct: number;
  isActive: boolean;
  signedIn: boolean;
  studentsJoined: number;
  payingStudents: number;
  earned: number;
  available: number;
  paid: number;
}

export type PayoutStatus = 'requested' | 'approved' | 'paid' | 'rejected';

export interface AdminPayout {
  id: number;
  partnerId: number;
  partnerName: string;
  amount: number;
  status: PayoutStatus;
  reference: string | null;
  adminNote: string | null;
  requestedAt: string;
  paidAt: string | null;
  /** Decrypted for sending money: {method: 'upi', upi} or {method: 'bank', holder, account, ifsc}. */
  payoutDetails: Record<string, string> | null;
  pan: string | null;
}
