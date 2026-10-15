import { QueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';

const MAX_RETRIES = 2;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount: number, error: unknown): boolean => {
          // Client errors (4xx) will not fix themselves on retry.
          if (isAxiosError(error)) {
            const status = error.response?.status;
            if (status !== undefined && status >= 400 && status < 500) return false;
          }
          return failureCount < MAX_RETRIES;
        },
      },
      mutations: { retry: false },
    },
  });
}
