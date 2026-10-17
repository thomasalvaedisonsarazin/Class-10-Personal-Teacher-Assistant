/** Web preview: Google Play payments exist only in the Android app. */
import type { BasePlanId, PlanChoice } from '@/lib/billing';
import type { BillingStatus, PurchaseResult } from '@/types/billing';

export interface PlanOffer {
  price: string;
  offerToken: string;
}

export interface StorePrices {
  plans?: Record<string, Partial<Record<BasePlanId, PlanOffer>>>;
  topic?: string;
}

export type BuyOutcome =
  | { status: 'done'; result: PurchaseResult }
  | { status: 'pending' }
  | { status: 'cancelled' };

export const isStoreAvailable = false;

const unavailable = (): Promise<never> =>
  Promise.reject(new Error('Payments work only in the Android app.'));

export const playStore = {
  loadPrices: (): Promise<StorePrices> => Promise.resolve({}),
  buy: (_choice: PlanChoice, _status: BillingStatus, _prices: StorePrices): Promise<BuyOutcome> =>
    unavailable(),
  syncPurchases: (): Promise<number> => Promise.resolve(0),
};
