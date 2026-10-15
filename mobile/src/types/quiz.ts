/** Quiz types. Correct answers only ever arrive in a graded result. */

export type QuestionType = 'mcq' | 'true_false' | 'fill_blank';

export interface QuizQuestion {
  questionId: number;
  position: number;
  type: QuestionType;
  stem: string;
  options: string[];
}

export interface QuizAttempt {
  attemptId: number;
  topicId: number;
  expiresAt: string;
  passPct: number;
  questions: QuizQuestion[];
}

export interface QuizAnswer {
  questionId: number;
  answer: string | null;
}

export interface QuestionResult {
  questionId: number;
  position: number;
  stem: string;
  options: string[];
  selectedAnswer: string | null;
  correctAnswer: string;
  isCorrect: boolean;
  explanation: string;
}

export interface QuizResult {
  attemptId: number;
  topicId: number;
  scorePct: number;
  correctCount: number;
  total: number;
  passed: boolean;
  passPct: number;
  results: QuestionResult[];
  nextTopic: { id: number; title: string } | null;
}
