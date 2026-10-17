import type { BillingStatus, PurchaseInput, PurchaseResult } from '@/types/billing';

import { api } from './api';

export const billingService = {
  /** My plan (student) or a linked child's plan (parent passes `studentId`). */
  async getStatus(studentId?: number): Promise<BillingStatus> {
    const { data } = await api.get<BillingStatus>('/billing/status', {
      params: studentId ? { studentId } : undefined,
    });
    return data;
  },

  /** The server checks the purchase with Google before unlocking anything. */
  async recordPurchase(input: PurchaseInput): Promise<PurchaseResult> {
    const { data } = await api.post<PurchaseResult>('/billing/purchases', input);
    return data;
  },
};
