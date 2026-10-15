/** Shared API types. API JSON is camelCase. Module agents add `src/types/<module>.ts`. */

export type Medium = 'en' | 'ta';

export type UserRole = 'student' | 'parent' | 'admin';

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
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}
