import {
  fetchProducts,
  finishTransaction,
  getAvailablePurchases,
  initConnection,
  isUserCancelledError,
  purchaseErrorListener,
  purchaseUpdatedListener,
  requestPurchase,
} from 'expo-iap';
import type { Purchase } from 'expo-iap';

import {
  BASE_PLAN_MONTHLY,
  BASE_PLAN_YEARLY,
  SUBSCRIPTION_IDS,
  TOPIC_PRODUCT_ID,
  isSubscriptionId,
  productIdFor,
  profileTagFor,
} from '@/lib/billing';
import type { BasePlanId, PlanChoice } from '@/lib/billing';
import type { BillingStatus, PurchaseResult } from '@/types/billing';

import { billingService } from './billingService';

export interface PlanOffer {
  price: string;
  offerToken: string;
}

/** Local prices from Google Play, per plan product and base plan (with offer tokens). */
export interface StorePrices {
  plans?: Record<string, Partial<Record<BasePlanId, PlanOffer>>>;
  topic?: string;
}

export type BuyOutcome =
  | { status: 'done'; result: PurchaseResult }
  | { status: 'pending' }
  | { status: 'cancelled' };

const BUY_TIMEOUT_MS = 5 * 60_000;

export const isStoreAvailable = true;

let connected: Promise<boolean> | null = null;

function connect(): Promise<boolean> {
  connected ??= initConnection().catch((err: unknown) => {
    connected = null;
    throw err;
  });
  return connected;
}

/** Prices and subscription offers for the Premium screen. */
async function loadPrices(): Promise<StorePrices> {
  await connect();
  const plans: NonNullable<StorePrices['plans']> = {};
  const subs = (await fetchProducts({ skus: [...SUBSCRIPTION_IDS], type: 'subs' })) ?? [];
  for (const product of subs) {
    if (product.type !== 'subs' || product.platform !== 'android') continue;
    const offers: Partial<Record<BasePlanId, PlanOffer>> = {};
    for (const offer of product.subscriptionOffers) {
      const token = offer.offerTokenAndroid;
      const basePlan = offer.basePlanIdAndroid;
      if (!token || (basePlan !== BASE_PLAN_MONTHLY && basePlan !== BASE_PLAN_YEARLY)) continue;
      // The first offer of each base plan is the normal price.
      offers[basePlan] ??= { price: offer.displayPrice, offerToken: token };
    }
    plans[product.id] = offers;
  }
  const prices: StorePrices = { plans };
  const items = (await fetchProducts({ skus: [TOPIC_PRODUCT_ID], type: 'in-app' })) ?? [];
  for (const product of items) {
    if (product.id === TOPIC_PRODUCT_ID) prices.topic = product.displayPrice;
  }
  return prices;
}

/** Wait for Google Play's answer to the purchase sheet. */
function waitForPurchase(productId: string): Promise<Purchase | null> {
  return new Promise((resolve, reject) => {
    const cleanup = (): void => {
      clearTimeout(timer);
      updated.remove();
      failed.remove();
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('Google Play did not answer. Please try again.'));
    }, BUY_TIMEOUT_MS);
    const updated = purchaseUpdatedListener((purchase: Purchase) => {
      if (purchase.productId !== productId) return;
      cleanup();
      resolve(purchase);
    });
    const failed = purchaseErrorListener((error) => {
      cleanup();
      if (isUserCancelledError(error)) resolve(null);
      else reject(new Error(error.message || 'The payment did not go through.'));
    });
  });
}

/** Read the student id out of the Google Play profile tag ("pta-12" or "pta-12-t40"). */
function studentIdFromTag(tag: string | null | undefined): number | undefined {
  const match = /^pta-(\d+)/.exec(tag ?? '');
  return match ? Number(match[1]) : undefined;
}

/** Hand a finished purchase to our server, then close it on the phone. */
async function deliver(purchase: Purchase, topicId?: number): Promise<PurchaseResult> {
  const token = purchase.purchaseToken;
  if (!token) throw new Error('Google Play did not return a purchase token.');
  const profileTag = 'obfuscatedProfileIdAndroid' in purchase ? purchase.obfuscatedProfileIdAndroid : null;
  const result = await billingService.recordPurchase({
    productId: purchase.productId,
    purchaseToken: token,
    studentId: studentIdFromTag(profileTag),
    topicId,
  });
  try {
    // The server already acknowledged/consumed it; this only clears the phone's queue.
    await finishTransaction({ purchase, isConsumable: !isSubscriptionId(purchase.productId) });
  } catch {
    // Already finished by the server: nothing to do.
  }
  return result;
}

/**
 * Open Google Play's payment sheet for `choice`, then unlock it on our server.
 * UPI payments can stay "pending" for a while; `syncPurchases` finishes them later.
 */
async function buy(
  choice: PlanChoice,
  status: BillingStatus,
  prices: StorePrices,
): Promise<BuyOutcome> {
  await connect();
  const productId = productIdFor(choice);
  const obfuscatedAccountId = status.accountTag;
  const obfuscatedProfileId = profileTagFor(status.profileTag, choice);
  const answer = waitForPurchase(productId);

  if (choice.kind === 'subscription') {
    const offer = prices.plans?.[choice.productId]?.[choice.basePlanId];
    if (!offer) throw new Error('This plan is not available right now. Please try again later.');
    await requestPurchase({
      type: 'subs',
      request: {
        google: {
          skus: [productId],
          subscriptionOffers: [{ sku: productId, offerToken: offer.offerToken }],
          obfuscatedAccountId,
          obfuscatedProfileId,
        },
      },
    });
  } else {
    await requestPurchase({
      type: 'in-app',
      request: { google: { skus: [productId], obfuscatedAccountId, obfuscatedProfileId } },
    });
  }

  const purchase = await answer;
  if (purchase === null) return { status: 'cancelled' };
  if (purchase.purchaseState === 'pending') return { status: 'pending' };
  const result = await deliver(purchase, choice.kind === 'topic' ? choice.topicId : undefined);
  return { status: 'done', result };
}

/** Finish purchases that were paid later (UPI) or interrupted. Returns how many unlocked. */
async function syncPurchases(): Promise<number> {
  await connect();
  const purchases = (await getAvailablePurchases()) ?? [];
  let unlocked = 0;
  for (const purchase of purchases) {
    if (purchase.purchaseState !== 'purchased') continue;
    try {
      await deliver(purchase);
      unlocked += 1;
    } catch {
      // Not ours, already used, or the server is unreachable: try again next time.
    }
  }
  return unlocked;
}

export const playStore = { loadPrices, buy, syncPurchases };
