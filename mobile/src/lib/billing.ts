/** Google Play product ids and plan rules (prices come from Google Play). */

/** One auto-renewing plan product per child (Google: one active subscription per product). */
export const SUBSCRIPTION_IDS = ['premium', 'premium_2', 'premium_3'] as const;
export const BASE_PLAN_MONTHLY = 'monthly';
export const BASE_PLAN_YEARLY = 'yearly';
export const TOPIC_PRODUCT_ID = 'topic_unlock';

export type BasePlanId = typeof BASE_PLAN_MONTHLY | typeof BASE_PLAN_YEARLY;

/** Shown until Google Play returns the real local prices. */
export const FALLBACK_PRICES = {
  monthly: '₹99',
  yearly: '₹999',
  topic: '₹75',
} as const;

export type PlanChoice =
  | { kind: 'subscription'; productId: string; basePlanId: BasePlanId }
  | { kind: 'topic'; topicId: number };

/** Monthly and yearly plans on the next free plan product; none when all are in use. */
export function planOptions(nextSubscriptionId: string | null): PlanChoice[] {
  if (nextSubscriptionId === null) return [];
  return [
    { kind: 'subscription', productId: nextSubscriptionId, basePlanId: BASE_PLAN_MONTHLY },
    { kind: 'subscription', productId: nextSubscriptionId, basePlanId: BASE_PLAN_YEARLY },
  ];
}

export function isSubscriptionId(productId: string): boolean {
  return (SUBSCRIPTION_IDS as readonly string[]).includes(productId);
}

/** Google Play profile id: the student, plus the topic for a single-topic purchase. */
export function profileTagFor(studentTag: string, choice: PlanChoice): string {
  return choice.kind === 'topic' ? `${studentTag}-t${choice.topicId}` : studentTag;
}

export function productIdFor(choice: PlanChoice): string {
  return choice.kind === 'subscription' ? choice.productId : TOPIC_PRODUCT_ID;
}

/** True when the plan is still running. */
export function isPremiumActive(premiumUntil: string | null, now: Date = new Date()): boolean {
  return premiumUntil !== null && new Date(premiumUntil).getTime() > now.getTime();
}

/** "17 Nov 2026" in Indian date format. */
export function formatUntil(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}
