import type { AuthTokens, Board, SubjectChoice, UpdateProfileInput, User } from '@/types/api';

import { api } from './api';
import { tokenStorage } from './tokenStorage';

export const authService = {
  async getMe(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
    return data;
  },

  /** Exchange a Google ID token for our access + refresh tokens. */
  async loginWithGoogle(idToken: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/google', { idToken });
    return data;
  },

  /** Email a 6-digit code (sign in, sign up or reset password). */
  async requestEmailCode(email: string): Promise<void> {
    await api.post('/auth/email/code', { email });
  },

  /** Sign in with an emailed code (a new email gets a new account). */
  async loginWithEmailCode(email: string, code: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/email/login', { email, code });
    return data;
  },

  /** Create an account with a password, or reset a forgotten one, using an emailed code. */
  async setPasswordWithCode(email: string, code: string, password: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/password/set', { email, code, password });
    return data;
  },

  async loginWithPassword(email: string, password: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/password/login', { email, password });
    return data;
  },

  /** Development builds only: sign in as a seeded test user. */
  async devLogin(email: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/dev-login', { email });
    return data;
  },

  async updateMe(input: UpdateProfileInput): Promise<User> {
    const { data } = await api.put<User>('/auth/me', input);
    return data;
  },

  /** Permanently delete the signed-in account and its data (not allowed for admins). */
  async deleteAccount(): Promise<void> {
    await api.delete('/auth/me');
  },

  async getBoards(): Promise<Board[]> {
    const { data } = await api.get<Board[]>('/boards');
    return data;
  },

  /** Every subject of a class (11th / 12th subject picker). */
  async getBoardSubjects(boardId: number): Promise<SubjectChoice[]> {
    const { data } = await api.get<SubjectChoice[]>(`/boards/${boardId}/subjects`);
    return data;
  },

  /** Keep this phone's session in use while the app is open (409 when another device has it). */
  async pingSession(): Promise<void> {
    await api.post('/auth/session/ping');
  },

  /** Free the account for another device (app closed / sent to the background). */
  async releaseSession(): Promise<void> {
    await api.post('/auth/session/release');
  },

  /** Best-effort server-side revoke; local tokens are cleared by the caller regardless. */
  async logout(): Promise<void> {
    const refreshToken = await tokenStorage.getRefreshToken();
    if (!refreshToken) {
      return;
    }
    await api.post('/auth/logout', { refreshToken });
  },
};
