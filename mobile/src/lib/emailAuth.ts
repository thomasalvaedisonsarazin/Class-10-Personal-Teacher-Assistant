/** Client-side checks for email sign-in (the server re-checks everything). */

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const PASSWORD_MIN_LENGTH = 8;

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

export function isValidEmail(value: string): boolean {
  return value.length <= 255 && EMAIL_PATTERN.test(normalizeEmail(value));
}

export function isValidCode(value: string): boolean {
  return /^\d{6}$/.test(value);
}

/** Keep only digits, at most 6 (for the code field). */
export function cleanCode(value: string): string {
  return value.replace(/\D/g, '').slice(0, 6);
}

/** A short reason the password is not allowed, or null when it is fine. */
export function passwordProblem(value: string): string | null {
  if (value.length < PASSWORD_MIN_LENGTH) {
    return `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  if (new TextEncoder().encode(value).length > 72) {
    return 'That password is too long.';
  }
  if (value.trim() !== value) {
    return 'Remove the spaces at the start or end.';
  }
  if (new Set(value).size < 4) {
    return 'Choose a stronger password.';
  }
  return null;
}
