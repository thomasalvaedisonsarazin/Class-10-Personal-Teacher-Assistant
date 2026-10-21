import type { PartnerDashboard, PartnerPayout, PayoutDetailsInput } from '@/types/partner';

import { api } from './api';

export const partnerService = {
  async dashboard(): Promise<PartnerDashboard> {
    const { data } = await api.get<PartnerDashboard>('/partner-program/me');
    return data;
  },

  async savePayoutDetails(input: PayoutDetailsInput): Promise<PartnerDashboard> {
    const { data } = await api.put<PartnerDashboard>('/partner-program/payout-details', input);
    return data;
  },

  async requestPayout(): Promise<PartnerPayout> {
    const { data } = await api.post<PartnerPayout>('/partner-program/payouts');
    return data;
  },

  /** Student: link my account to the school / teacher whose code I have. */
  async useReferralCode(code: string): Promise<string> {
    const { data } = await api.post<{ partnerName: string }>('/referrals', { code });
    return data.partnerName;
  },
};
