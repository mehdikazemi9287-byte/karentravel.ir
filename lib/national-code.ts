/* Iranian national code (کد ملی) helpers — the same rule the API enforces (backend/app/traveller_identity.py). */
const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹';
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩';

/** Persian/Arabic digits to ASCII; spaces and dashes removed. */
export function normalizeDigits(value: string): string {
  return value.replace(/[۰-۹]/g, d => String(FA_DIGITS.indexOf(d))).replace(/[٠-٩]/g, d => String(AR_DIGITS.indexOf(d))).replace(/[\s-]/g, '');
}

/** 10 digits, not one repeated digit, last digit is the check digit. */
export function isValidNationalCode(value: string): boolean {
  const code = normalizeDigits(value);
  if (!/^\d{10}$/.test(code) || new Set(code).size === 1) return false;
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += Number(code[i]) * (10 - i);
  const remainder = sum % 11;
  const check = Number(code[9]);
  return remainder < 2 ? check === remainder : check === 11 - remainder;
}

export const NATIONAL_CODE_ERROR = 'کد ملی معتبر نیست؛ ۱۰ رقم کد ملی را دوباره بررسی کنید';
