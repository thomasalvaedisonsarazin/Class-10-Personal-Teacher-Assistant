/**
 * Public, non-secret runtime config (EXPO_PUBLIC_* are inlined at build time).
 * Never put API keys or secrets here.
 */
const rawApiUrl = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000';

export const env = {
  apiUrl: rawApiUrl.replace(/\/+$/, ''),
  googleAndroidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? '',
  googleWebClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? '',
  enableDevLogin: __DEV__ && process.env.EXPO_PUBLIC_ENABLE_DEV_LOGIN === 'true',
} as const;

export const API_BASE_URL = `${env.apiUrl}/api/v1`;
