/** Curriculum + progress types (API JSON is camelCase). */

/** locked: pass the previous topic first · available: open · active: started · completed: passed (review). */
export type TopicStatus = 'locked' | 'available' | 'active' | 'completed';

/** Payments: free topic, open through a plan, bought on its own, or needs payment. */
export type TopicAccess = 'free' | 'premium' | 'purchased' | 'payment_required';

export interface CurrentTopic {
  id: number;
  title: string;
  status: TopicStatus;
}

export interface SubjectSummary {
  id: number;
  name: string;
  tileColor: string;
  icon: string;
  totalTopics: number;
  completedTopics: number;
  /** First unfinished topic; null when the whole subject is finished. */
  currentTopic: CurrentTopic | null;
}

export interface TopicItem {
  id: number;
  title: string;
  status: TopicStatus;
  bestScorePct: number | null;
  /** Missing on older servers: treat as free. */
  access?: TopicAccess;
}

export interface ChapterWithTopics {
  id: number;
  title: string;
  topics: TopicItem[];
}

export interface SubjectDetail extends SubjectSummary {
  chapters: ChapterWithTopics[];
}

export interface TopicDetail {
  id: number;
  title: string;
  learningObjectives: string;
  status: TopicStatus;
  bestScorePct: number | null;
  access?: TopicAccess;
  chapterTitle: string;
  subject: { id: number; name: string; tileColor: string };
  passPct: number;
}

/** Consecutive study days (India time). */
export interface Streak {
  current: number;
  longest: number;
  studiedToday: boolean;
}
