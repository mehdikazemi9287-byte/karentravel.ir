import type { FormEvent } from 'react';

/** Persian messages instead of the browser's English constraint-validation bubble (QA D12).
 *  Spread the result on an <input>; the message is cleared as soon as the value changes. */
export function persianValidity(messages: { missing: string; pattern?: string }) {
  return {
    onInvalid: (event: FormEvent<HTMLInputElement>) => {
      const input = event.currentTarget;
      input.setCustomValidity(input.validity.valueMissing ? messages.missing : messages.pattern || messages.missing);
    },
    onInput: (event: FormEvent<HTMLInputElement>) => { event.currentTarget.setCustomValidity(''); },
  };
}

export const MOBILE_VALIDITY = { missing: 'شماره همراه را وارد کنید.', pattern: 'شماره همراه باید ۱۱ رقم و با ۰۹ شروع شود؛ مثل ۰۹۱۲۱۲۳۴۵۶۷.' };
export const OTP_VALIDITY = { missing: 'کد شش‌رقمی پیامک را وارد کنید.', pattern: 'کد ورود باید ۶ رقم باشد.' };
