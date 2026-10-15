import axios, { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

import { authEvents } from '@/lib/authEvents';
import { API_BASE_URL } from '@/lib/env';
import type { ApiError, AuthTokens } from '@/types/api';

import { tokenStorage } from './tokenStorage';

const REQUEST_TIMEOUT_MS = 20_000;
const REFRESH_PATH = '/auth/refresh';

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

/** Bare client for the refresh call so it never goes through the 401 interceptor. */
const refreshClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(async (config) => {
  const token = await tokenStorage.getAccessToken();
  if (token) {
    const headers = AxiosHeaders.from(config.headers);
    headers.set('Authorization', `Bearer ${token}`);
    config.headers = headers;
  }
  return config;
});

let refreshInFlight: Promise<string | null> | null = null;

async function performRefresh(): Promise<string | null> {
  const refreshToken = await tokenStorage.getRefreshToken();
  if (!refreshToken) {
    return null;
  }
  try {
    const { data } = await refreshClient.post<AuthTokens>(REFRESH_PATH, { refreshToken });
    await tokenStorage.setTokens(data);
    return data.accessToken;
  } catch {
    return null;
  }
}

/** Ensures only one POST /auth/refresh runs at a time; concurrent 401s share it. */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function forceLogout(): Promise<void> {
  try {
    await tokenStorage.clear();
  } finally {
    authEvents.emitLogout();
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || !error.config) {
      return Promise.reject(error);
    }
    const original = error.config as RetriableRequestConfig;
    const isRefreshCall = original.url?.includes(REFRESH_PATH) ?? false;

    if (error.response?.status !== 401 || original._retry || isRefreshCall) {
      if (error.response?.status === 401 && original._retry) {
        await forceLogout();
      }
      return Promise.reject(error);
    }

    original._retry = true;
    const newToken = await refreshAccessToken();
    if (!newToken) {
      await forceLogout();
      return Promise.reject(error);
    }

    const headers = AxiosHeaders.from(original.headers);
    headers.set('Authorization', `Bearer ${newToken}`);
    original.headers = headers;
    return api(original);
  },
);

function isApiErrorBody(value: unknown): value is ApiError {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false;
  }
  const inner = (value as { error: unknown }).error;
  return (
    typeof inner === 'object' &&
    inner !== null &&
    'message' in inner &&
    typeof (inner as { message: unknown }).message === 'string'
  );
}

const FALLBACK_MESSAGE = 'Something went wrong. Please try again.';
const NETWORK_MESSAGE = 'Unable to reach the server. Check your internet connection.';

/** Human-readable message from any thrown value; reads `{ error: { code, message } }`. */
export function getApiErrorMessage(err: unknown): string {
  if (err instanceof AxiosError || axios.isAxiosError(err)) {
    const body: unknown = err.response?.data;
    if (isApiErrorBody(body)) {
      return body.error.message;
    }
    if (!err.response) {
      return NETWORK_MESSAGE;
    }
    return FALLBACK_MESSAGE;
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return FALLBACK_MESSAGE;
}

/** Machine-readable error code from the API envelope, if present. */
export function getApiErrorCode(err: unknown): string | null {
  if (axios.isAxiosError(err) && isApiErrorBody(err.response?.data)) {
    return (err.response?.data as ApiError).error.code;
  }
  return null;
}
