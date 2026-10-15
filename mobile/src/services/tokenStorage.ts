import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import type { AuthTokens } from '@/types/api';

const ACCESS_TOKEN_KEY = 'pta.accessToken';
const REFRESH_TOKEN_KEY = 'pta.refreshToken';

interface KeyValueStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

/** Device keystore (Android Keystore via expo-secure-store). */
const secureStore: KeyValueStore = {
  get: (key) => SecureStore.getItemAsync(key),
  set: (key, value) => SecureStore.setItemAsync(key, value),
  remove: (key) => SecureStore.deleteItemAsync(key),
};

/**
 * Browser preview only (expo-secure-store has no web implementation).
 * sessionStorage is cleared when the tab closes; the Android app never uses this.
 */
const webSessionStore: KeyValueStore = {
  get: async (key) => {
    try {
      return globalThis.sessionStorage?.getItem(key) ?? null;
    } catch {
      return null;
    }
  },
  set: async (key, value) => {
    try {
      globalThis.sessionStorage?.setItem(key, value);
    } catch {
      // Storage blocked (private mode): session lasts until reload.
    }
  },
  remove: async (key) => {
    try {
      globalThis.sessionStorage?.removeItem(key);
    } catch {
      // Nothing to clear.
    }
  },
};

const store: KeyValueStore = Platform.OS === 'web' ? webSessionStore : secureStore;

/** Tokens are kept in the device keystore (expo-secure-store), never in AsyncStorage. */
export const tokenStorage = {
  async getAccessToken(): Promise<string | null> {
    return store.get(ACCESS_TOKEN_KEY);
  },

  async getRefreshToken(): Promise<string | null> {
    return store.get(REFRESH_TOKEN_KEY);
  },

  async getTokens(): Promise<AuthTokens | null> {
    const [accessToken, refreshToken] = await Promise.all([
      store.get(ACCESS_TOKEN_KEY),
      store.get(REFRESH_TOKEN_KEY),
    ]);
    if (!accessToken || !refreshToken) {
      return null;
    }
    return { accessToken, refreshToken };
  },

  async setTokens(tokens: AuthTokens): Promise<void> {
    await Promise.all([
      store.set(ACCESS_TOKEN_KEY, tokens.accessToken),
      store.set(REFRESH_TOKEN_KEY, tokens.refreshToken),
    ]);
  },

  async clear(): Promise<void> {
    await Promise.all([store.remove(ACCESS_TOKEN_KEY), store.remove(REFRESH_TOKEN_KEY)]);
  },
};
