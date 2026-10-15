import type { User } from '@/types/api';

import { api } from './api';
import { tokenStorage } from './tokenStorage';

export const authService = {
  async getMe(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
    return data;
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
