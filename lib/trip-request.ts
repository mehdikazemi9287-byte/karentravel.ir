/* Outcome of POST /public/sales-desk/requests (offline sales request, Launch V1 item 7).
 *
 * Honest by construction: the form says "received" only for a 2xx answer that carries {received: true}.
 * 503 means the public intake is not configured on this server (no SALES_DESK_PUBLIC_TENANT and no consumer
 * tenant): the request was NOT stored, and the visitor is told so — never a success message.
 */
export type RequestOutcome = {kind: 'done'} | {kind: 'inactive'} | {kind: 'error'; message: string};

export const INACTIVE_TITLE = 'ثبت آنلاین درخواست هنوز فعال نشده است';
export const INACTIVE_TEXT = 'درخواست شما ثبت نشد. تا فعال‌شدن این بخش، لطفاً با پشتیبانی تماس بگیرید تا کارشناس درخواستتان را تلفنی ثبت کند.';

/** The visitor-facing outcome for a reply (a 2xx body) or an error status (0 = network failure). */
export function requestOutcome(reply: {status: number; body?: unknown}): RequestOutcome {
  const {status, body} = reply;
  if (status >= 200 && status < 300) {
    return body !== null && typeof body === 'object' && (body as {received?: unknown}).received === true
      ? {kind: 'done'} : {kind: 'error', message: 'پاسخ سامانه نامشخص بود و ثبت درخواست تأیید نشد؛ لطفاً با پشتیبانی تماس بگیرید.'};
  }
  if (status === 503) return {kind: 'inactive'};
  if (status === 422) return {kind: 'error', message: 'نام، شمارهٔ موبایل و سفر موردنظر را درست وارد کنید و رضایت تماس را تأیید کنید.'};
  if (status === 429) return {kind: 'error', message: 'درخواست‌ها زیاد بوده؛ کمی بعد دوباره تلاش کنید.'};
  return {kind: 'error', message: 'ارسال انجام نشد؛ اتصال را بررسی کنید و دوباره تلاش کنید.'};
}
