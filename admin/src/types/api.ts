/** Shapes shared with the FastAPI backend. All API JSON is camelCase. */

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
}

export type Medium = 'en' | 'ta';

export type UserRole = 'student' | 'parent' | 'admin';

export interface User {
  id: number;
  email: string;
  fullName: string | null;
  avatarUrl: string | null;
  role: UserRole;
  boardId: number | null;
  medium: Medium;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType?: string;
}
