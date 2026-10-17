/** Payments (Google Play Billing). API JSON is camelCase. */

export interface BillingStatus {
  billingEnabled: boolean;
  studentId: number;
  /** ISO time the plan or pass ends; null when there is none. */
  premiumUntil: string | null;
  purchasedTopicIds: number[];
  freeTopicsPerSubject: number;
  /** Plan product to buy next (premium, premium_2, premium_3); null when all are in use. */
  nextSubscriptionId: string | null;
  /** Sent to Google Play as obfuscatedAccountId / obfuscatedProfileId. */
  accountTag: string;
  profileTag: string;
}

export interface PurchaseInput {
  productId: string;
  purchaseToken: string;
  studentId?: number;
  topicId?: number;
}

export interface PurchaseResult {
  kind: 'subscription' | 'pass' | 'topic';
  studentId: number;
  topicId: number | null;
  expiresAt: string | null;
}
