import type { AuthTokens } from '@/types/api';

const ACCESS_KEY = 'pta_admin_access_token';
const REFRESH_KEY = 'pta_admin_refresh_token';

let memoryAccess: string | null = null;
let memoryRefresh: string | null = null;

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Storage unavailable (private mode, blocked site data); the memory copy still works.
  }
}

/** Tokens live in memory first and are mirrored to localStorage when it is available. */
export const tokenStorage = {
  getAccessToken(): string | null {
    if (memoryAccess === null) memoryAccess = readStorage(ACCESS_KEY);
    return memoryAccess;
  },
  getRefreshToken(): string | null {
    if (memoryRefresh === null) memoryRefresh = readStorage(REFRESH_KEY);
    return memoryRefresh;
  },
  setTokens(tokens: AuthTokens): void {
    memoryAccess = tokens.accessToken;
    memoryRefresh = tokens.refreshToken;
    writeStorage(ACCESS_KEY, tokens.accessToken);
    writeStorage(REFRESH_KEY, tokens.refreshToken);
  },
  clear(): void {
    memoryAccess = null;
    memoryRefresh = null;
    writeStorage(ACCESS_KEY, null);
    writeStorage(REFRESH_KEY, null);
  },
};
