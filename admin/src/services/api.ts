import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

import { emitLogout } from '@/lib/authEvents';
import { API_BASE_URL } from '@/lib/env';
import { tokenStorage } from '@/lib/tokenStorage';
import type { ApiError, AuthTokens } from '@/types/api';

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

/** Endpoints where a 401 means "bad credentials", never "refresh and retry". */
const NO_REFRESH_PATHS = ['/auth/refresh', '/auth/google', '/auth/dev-login', '/auth/logout'];

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
});

api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

let refreshInFlight: Promise<string> | null = null;

async function requestNewAccessToken(): Promise<string> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }
  // Plain axios (not `api`) so this call never re-enters the interceptors.
  const { data } = await axios.post<AuthTokens>(`${API_BASE_URL}/auth/refresh`, { refreshToken });
  tokenStorage.setTokens(data);
  return data.accessToken;
}

/** Shares one refresh request between every request that hit a 401 at the same time. */
function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    refreshInFlight = requestNewAccessToken().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

function shouldAttemptRefresh(
  config: RetriableRequestConfig | undefined,
): config is RetriableRequestConfig {
  if (!config || config._retry) return false;
  const url = config.url ?? '';
  return !NO_REFRESH_PATHS.some((path) => url.includes(path));
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableRequestConfig | undefined;
    if (error.response?.status !== 401 || !shouldAttemptRefresh(config)) {
      return Promise.reject(error);
    }

    config._retry = true;
    let accessToken: string;
    try {
      accessToken = await refreshAccessToken();
    } catch {
      tokenStorage.clear();
      emitLogout();
      return Promise.reject(error);
    }
    config.headers.set('Authorization', `Bearer ${accessToken}`);
    return api(config);
  },
);

export function isApiError(value: unknown): value is ApiError {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false;
  const body: unknown = (value as { error: unknown }).error;
  return (
    typeof body === 'object' &&
    body !== null &&
    typeof (body as { message?: unknown }).message === 'string'
  );
}

const DEFAULT_ERROR_MESSAGE = 'Something went wrong. Please try again.';

/** Turns anything thrown by an API call into a message that is safe to show. */
export function getApiErrorMessage(err: unknown, fallback: string = DEFAULT_ERROR_MESSAGE): string {
  if (axios.isAxiosError(err)) {
    const data: unknown = err.response?.data;
    if (isApiError(data)) return data.error.message;
    if (!err.response) return 'Unable to reach the server. Check your connection and try again.';
    return fallback;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

/** Error code from the backend envelope, if there is one. */
export function getApiErrorCode(err: unknown): string | null {
  if (axios.isAxiosError(err)) {
    const data: unknown = err.response?.data;
    if (isApiError(data)) return data.error.code;
  }
  return null;
}

export default api;
