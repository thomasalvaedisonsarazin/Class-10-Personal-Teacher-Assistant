/** Typed access to public build-time configuration. */
export const env = {
  apiUrl: (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, ''),
  googleClientId: import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '',
  enableDevLogin: import.meta.env.VITE_ENABLE_DEV_LOGIN === 'true',
} as const;

export const API_BASE_URL = `${env.apiUrl}/api/v1`;
