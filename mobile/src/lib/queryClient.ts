import { QueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';

const MAX_RETRIES = 2;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        // Never retry client errors (401/403/404/409…); retry network/5xx a couple of times.
        if (isAxiosError(error)) {
          const status = error.response?.status;
          if (status !== undefined && status >= 400 && status < 500) {
            return false;
          }
        }
        return failureCount < MAX_RETRIES;
      },
    },
    mutations: {
      retry: false,
    },
  },
});
