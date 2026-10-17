import { describe, expect, it } from '@jest/globals';

import {
  TOPIC_PRODUCT_ID,
  isPremiumActive,
  isSubscriptionId,
  planOptions,
  productIdFor,
  profileTagFor,
} from '@/lib/billing';

describe('planOptions', () => {
  it('offers monthly and yearly auto-renewing plans on the next plan product', () => {
    expect(planOptions('premium_2')).toEqual([
      { kind: 'subscription', productId: 'premium_2', basePlanId: 'monthly' },
      { kind: 'subscription', productId: 'premium_2', basePlanId: 'yearly' },
    ]);
  });

  it('offers no plan when all plan products are in use', () => {
    expect(planOptions(null)).toEqual([]);
  });
});

describe('product and profile tags', () => {
  it('maps choices to Google Play product ids', () => {
    const yearly = { kind: 'subscription', productId: 'premium_3', basePlanId: 'yearly' } as const;
    expect(productIdFor(yearly)).toBe('premium_3');
    expect(productIdFor({ kind: 'topic', topicId: 4 })).toBe(TOPIC_PRODUCT_ID);
    expect(isSubscriptionId('premium_2')).toBe(true);
    expect(isSubscriptionId(TOPIC_PRODUCT_ID)).toBe(false);
  });

  it('keeps the topic inside the Google purchase for single topics', () => {
    const monthly = { kind: 'subscription', productId: 'premium', basePlanId: 'monthly' } as const;
    expect(profileTagFor('pta-12', { kind: 'topic', topicId: 40 })).toBe('pta-12-t40');
    expect(profileTagFor('pta-12', monthly)).toBe('pta-12');
  });
});

describe('isPremiumActive', () => {
  const now = new Date('2026-10-17T12:00:00Z');

  it('is active only before the end time', () => {
    expect(isPremiumActive('2026-11-17T12:00:00Z', now)).toBe(true);
    expect(isPremiumActive('2026-10-01T12:00:00Z', now)).toBe(false);
    expect(isPremiumActive(null, now)).toBe(false);
  });
});
