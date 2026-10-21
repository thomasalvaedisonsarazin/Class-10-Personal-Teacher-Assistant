/** Shared API types. API JSON is camelCase. Module agents add `src/types/<module>.ts`. */

export type Medium = 'en' | 'ta';

/** Lesson explanation language; Tanglish = Tamil sentences with English technical words. */
export type LessonLanguage = 'en' | 'ta' | 'tanglish';

export type UserRole = 'student' | 'parent' | 'admin' | 'partner';

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown> | unknown[] | null;
}

/** Error envelope returned by the backend: `{ error: { code, message } }`. */
export interface ApiError {
  error: ApiErrorBody;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface User {
  id: number;
  email: string;
  fullName: string | null;
  avatarUrl: string | null;
  role: UserRole;
  boardId: number | null;
  medium: Medium | null;
  /** Preferred explanation language (null = same as medium). */
  lessonLanguage: LessonLanguage | null;
  /** True when the user can also sign in with email + password. */
  hasPassword?: boolean;
  /** School / teacher partner this student joined with (null when none). */
  referredByPartnerId?: number | null;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType?: string;
  /** Access-token lifetime in seconds. */
  expiresIn?: number;
  user?: User;
}

export interface Board {
  id: number;
  code: string;
  name: string;
}

export interface UpdateProfileInput {
  fullName?: string;
  boardId?: number;
  medium?: Medium;
  lessonLanguage?: LessonLanguage;
  /** Only during setup. */
  role?: 'student' | 'parent';
}
