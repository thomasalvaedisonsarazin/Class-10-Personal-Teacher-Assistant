/** Parent ↔ student linking and reports (API JSON is camelCase). */
import type { Medium } from './api';
import type { TopicStatus } from './curriculum';

export interface Invite {
  code: string;
  expiresAt: string;
}

export interface LinkedParent {
  linkId: number;
  name: string | null;
  email: string;
  status: 'pending' | 'accepted' | 'revoked';
  linkedAt: string | null;
}

export interface StudentLinks {
  parents: LinkedParent[];
  invite: Invite | null;
}

export interface SubjectProgress {
  subjectId: number;
  name: string;
  tileColor: string;
  completed: number;
  total: number;
}

export interface ChildSummary {
  studentId: number;
  name: string | null;
  medium: Medium | null;
  topicsCompleted: number;
  topicsTotal: number;
  subjects: SubjectProgress[];
  lastActiveAt: string | null;
  testsThisWeek: number;
  averageScoreThisWeek: number | null;
}

export interface SubjectReport extends SubjectProgress {
  topics: { title: string; status: TopicStatus; bestScorePct: number | null }[];
}

export interface TestResult {
  topicTitle: string;
  subjectName: string;
  scorePct: number;
  passed: boolean;
  submittedAt: string;
}

export interface ChildReport extends ChildSummary {
  subjectsDetail: SubjectReport[];
  recentTests: TestResult[];
  minutesLearningThisWeek: number;
  reExplanationsThisWeek: number;
}
