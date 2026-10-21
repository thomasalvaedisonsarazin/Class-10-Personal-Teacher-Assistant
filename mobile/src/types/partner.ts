/** School / teacher partner program (amounts in rupees). */

export type PayoutStatus = 'requested' | 'approved' | 'paid' | 'rejected';

export interface PartnerPayout {
  id: number;
  amount: number;
  status: PayoutStatus;
  reference: string | null;
  requestedAt: string;
  paidAt: string | null;
}

export interface PartnerDashboard {
  name: string;
  code: string;
  shareLink: string;
  commissionPct: number;
  studentsJoined: number;
  payingStudents: number;
  earned: number;
  onHold: number;
  available: number;
  requested: number;
  paid: number;
  payoutMinimum: number;
  holdDays: number;
  canRequestPayout: boolean;
  /** Masked, e.g. "UPI ••••@okhdfc" or "Bank ••••1234". */
  payoutMethod: string | null;
  panAdded: boolean;
  payouts: PartnerPayout[];
}

export type PayoutDetailsInput =
  | { method: 'upi'; upiId: string; pan?: string }
  | { method: 'bank'; holderName: string; accountNumber: string; ifsc: string; pan?: string };
