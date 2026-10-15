import api from '@/services/api';
import type { AuthTokens, User } from '@/types/api';

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}

export async function loginWithGoogle(idToken: string): Promise<AuthTokens> {
  const { data } = await api.post<AuthTokens>('/auth/google', { idToken });
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  await api.post('/auth/logout', { refreshToken });
}
