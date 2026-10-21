/** School / teacher referral codes. */

import * as Application from 'expo-application';
import { Platform } from 'react-native';

/** Upper-case and drop spaces / dashes, like the server does. */
export function normalizeReferralCode(value: string): string {
  return value.toUpperCase().replace(/[^A-Z0-9]/g, '');
}

/** Read the code from a Play install referrer such as "pta_ref=STJOSE7K2&utm_source=…". */
export function codeFromReferrer(referrer: string | null | undefined): string | null {
  if (!referrer) return null;
  for (const part of referrer.split('&')) {
    const [key, value] = part.split('=');
    if (key === 'pta_ref' && value) {
      const code = normalizeReferralCode(decodeURIComponent(value));
      return code.length >= 3 ? code : null;
    }
  }
  return null;
}

/** The code from the partner's link the app was installed through (Android only). */
export async function installReferralCode(): Promise<string | null> {
  if (Platform.OS !== 'android') return null;
  try {
    return codeFromReferrer(await Application.getInstallReferrerAsync());
  } catch {
    return null;
  }
}

/** "₹1,234.50" in Indian format. */
export function formatRupees(value: number): string {
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}
