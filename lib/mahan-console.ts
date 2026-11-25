/* Pure helpers for the staff Mahan (W5) test console (components/panel/MahanConsolePanel.tsx).
 * Validation mirrors the API's own checks (backend/app/mahan_flight.py: SearchIn, PassengerIn, HoldIn); the API stays the
 * authority. Persian/Arabic digits are converted to Latin before any check (lessons: never strip them with /\D/). */

const FA = '۰۱۲۳۴۵۶۷۸۹';
const AR = '٠١٢٣٤٥٦٧٨٩';

/** Persian/Arabic digits → ASCII; nothing else is changed. */
export function latinDigits(value: string): string {
  return String(value ?? '').replace(/[۰-۹]/g, d => String(FA.indexOf(d))).replace(/[٠-٩]/g, d => String(AR.indexOf(d)));
}

/** A Gregorian date typed as YYYY-MM-DD or YYYY/MM/DD (any digits) → ISO, or null if it is not a real date. */
export function isoDate(value: string): string | null {
  const m = latinDigits(value).trim().match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
  return `${String(y).padStart(4, '0')}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

/** 10–15 digits with an optional leading +, as the API accepts; spaces and dashes are removed. */
export function normalizePhone(value: string): string {
  return latinDigits(value).replace(/[\s\-()]/g, '');
}
export const isPhone = (value: string) => /^\+?[0-9]{10,15}$/.test(normalizePhone(value));

export type PaxType = 'ADT' | 'CHD' | 'INF';
export const PAX_FA: Record<PaxType, string> = {ADT: 'بزرگسال', CHD: 'کودک', INF: 'نوزاد'};

export type SearchForm = {origin: string; destination: string; depart_on: string; return_on: string; trip: 'one_way' | 'round_trip'; adults: string; children: string; infants: string};
export type SearchBody = {origin: string; destination: string; depart_on: string; return_on?: string; adults: number; children: number; infants: number};

/** Search form → API body, or the list of problems (Persian). Mirrors SearchIn and flight_port.validate_search basics. */
export function searchBody(f: SearchForm, today: string): {body?: SearchBody; errors: string[]} {
  const errors: string[] = [];
  const o = f.origin.trim().toUpperCase(), d = f.destination.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(o)) errors.push('مبدأ باید کد سه‌حرفی لاتین فرودگاه باشد (مثل IKA).');
  if (!/^[A-Z]{3}$/.test(d)) errors.push('مقصد باید کد سه‌حرفی لاتین فرودگاه باشد (مثل BKK).');
  if (o && o === d) errors.push('مبدأ و مقصد نباید یکی باشند.');
  const dep = isoDate(f.depart_on);
  if (!dep) errors.push('تاریخ رفت معتبر نیست (میلادی، به شکل 2026-12-01).');
  else if (dep < today) errors.push('تاریخ رفت گذشته است.');
  let ret: string | undefined;
  if (f.trip === 'round_trip') {
    const r = isoDate(f.return_on);
    if (!r) errors.push('تاریخ برگشت معتبر نیست.');
    else if (dep && r < dep) errors.push('تاریخ برگشت نباید پیش از تاریخ رفت باشد.');
    else ret = r;
  }
  const n = (s: string) => {const t = latinDigits(s).trim(); return /^\d+$/.test(t) ? Number(t) : NaN;};
  const adults = n(f.adults), children = n(f.children || '0'), infants = n(f.infants || '0');
  if (!Number.isInteger(adults) || adults < 1 || adults > 9) errors.push('تعداد بزرگسال باید بین ۱ تا ۹ باشد.');
  if (!Number.isInteger(children) || children < 0 || children > 8) errors.push('تعداد کودک باید بین ۰ تا ۸ باشد.');
  if (!Number.isInteger(infants) || infants < 0) errors.push('تعداد نوزاد معتبر نیست.');
  else if (Number.isInteger(adults) && infants > adults) errors.push('هر نوزاد به یک بزرگسال نیاز دارد.');
  if (Number.isInteger(adults) && Number.isInteger(children) && adults + children > 9) errors.push('جمع بزرگسال و کودک حداکثر ۹ نفر است.');
  if (errors.length) return {errors};
  return {errors, body: {origin: o, destination: d, depart_on: dep!, ...(ret ? {return_on: ret} : {}), adults, children, infants}};
}

export type PassengerForm = {type: PaxType; first_name: string; last_name: string; gender: '' | 'M' | 'F'; birth_date: string; document_type: 'P' | 'I'; document_number: string; document_expiry: string; nationality: string};
export type PassengerBody = Omit<PassengerForm, 'gender'> & {gender: 'M' | 'F'};

export function emptyPassengers(counts: {adults: number; children: number; infants: number}): PassengerForm[] {
  const one = (type: PaxType): PassengerForm => ({type, first_name: '', last_name: '', gender: '', birth_date: '', document_type: 'P', document_number: '', document_expiry: '', nationality: 'IRN'});
  return [...Array(counts.adults).fill('ADT'), ...Array(counts.children).fill('CHD'), ...Array(counts.infants).fill('INF')].map(one);
}

/** Whole years between two ISO dates. */
export function ageOn(birthIso: string, onIso: string): number {
  const [by, bm, bd] = birthIso.split('-').map(Number); const [y, m, d] = onIso.split('-').map(Number);
  return y - by - (m < bm || (m === bm && d < bd) ? 1 : 0);
}

/** One passenger → API body, or the field problems (Persian). Mirrors PassengerIn + the hold's date checks; the age bands
 *  (infant < 2, child 2–11, adult 12+ on the first departure day) are the usual airline bands and are checked here only to
 *  help staff — the API and Mahan decide. */
export function validatePassenger(p: PassengerForm, today: string, departOn: string): {body?: PassengerBody; errors: Partial<Record<keyof PassengerForm, string>>} {
  const errors: Partial<Record<keyof PassengerForm, string>> = {};
  const first = p.first_name.trim().replace(/\s+/g, ' '), last = p.last_name.trim().replace(/\s+/g, ' ');
  const name = /^[A-Za-z][A-Za-z ]{0,39}$/;
  if (!name.test(first)) errors.first_name = 'نام را با حروف لاتین، همان‌طور که در گذرنامه آمده، بنویسید.';
  if (!name.test(last)) errors.last_name = 'نام خانوادگی را با حروف لاتین، همان‌طور که در گذرنامه آمده، بنویسید.';
  if (p.gender !== 'M' && p.gender !== 'F') errors.gender = 'جنسیت را انتخاب کنید.';
  const birth = isoDate(p.birth_date);
  if (!birth) errors.birth_date = 'تاریخ تولد میلادی معتبر نیست (مثل 1990-05-21).';
  else if (birth >= today) errors.birth_date = 'تاریخ تولد باید پیش از امروز باشد.';
  else {
    const age = ageOn(birth, departOn);
    if (p.type === 'INF' && age >= 2) errors.birth_date = 'نوزاد در روز پرواز باید زیر ۲ سال باشد.';
    if (p.type === 'CHD' && (age < 2 || age >= 12)) errors.birth_date = 'کودک در روز پرواز باید ۲ تا ۱۱ سال باشد.';
    if (p.type === 'ADT' && age < 12) errors.birth_date = 'بزرگسال در روز پرواز باید ۱۲ سال یا بیشتر باشد.';
  }
  const doc = latinDigits(p.document_number).replace(/[\s-]/g, '').toUpperCase();
  if (!/^[A-Z0-9]{5,20}$/.test(doc)) errors.document_number = 'شمارهٔ مدرک ۵ تا ۲۰ حرف یا رقم لاتین است.';
  else if (p.document_type === 'I' && !/^\d{10}$/.test(doc)) errors.document_number = 'کد ملی باید ۱۰ رقم باشد.';
  const expiry = isoDate(p.document_expiry);
  if (!expiry) errors.document_expiry = 'تاریخ اعتبار مدرک معتبر نیست (میلادی).';
  else if (expiry <= today) errors.document_expiry = 'اعتبار مدرک تمام شده است.';
  else if (expiry < departOn) errors.document_expiry = 'اعتبار مدرک پیش از روز پرواز تمام می‌شود.';
  const nat = p.nationality.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(nat)) errors.nationality = 'ملیت کد سه‌حرفی لاتین است (مثل IRN).';
  if (Object.keys(errors).length) return {errors};
  return {errors, body: {type: p.type, first_name: first, last_name: last, gender: p.gender as 'M' | 'F', birth_date: birth!, document_type: p.document_type,
    document_number: doc, document_expiry: expiry!, nationality: nat}};
}

/* ---- Idempotency-Key per hold attempt ----
 * A key belongs to one hold attempt. The API stores the outcome under the key and replays it for the same key + body.
 *  - 'done'  : the hold answered (held) — the offer is finished; no further hold for it from this screen.
 *  - 'stop'  : Mahan's answer was lost (status unknown) — a PNR may exist. Never retry; staff checks NRSRT / the holds list.
 *  - 'reuse' : we do not know whether the server processed the request (network failure, 5xx, in progress, session refresh).
 *              A retry must send the SAME key so the server replays its stored result instead of booking twice.
 *  - 'new'   : the server answered with a definite refusal (price changed, refused, expired, invalid). That outcome is stored
 *              under the old key, so a retry needs a FRESH key (the old one would only replay the refusal). */
export type KeyNext = 'done' | 'stop' | 'reuse' | 'new';
export function afterHold(outcome: {status?: string; httpStatus?: number; code?: string}): KeyNext {
  if (outcome.status === 'held') return 'done';
  if (outcome.status === 'unknown') return 'stop';
  if (outcome.status === 'price_changed' || outcome.status === 'not_held') return 'new';     // a replayed stored refusal (HTTP 201/200)
  const s = outcome.httpStatus ?? 0;
  if (s === 0 || s === 401 || s >= 500 || outcome.code === 'HOLD_IN_PROGRESS') return 'reuse';
  if (s === 409 && outcome.code === 'IDEMPOTENCY_MISMATCH') return 'reuse';               // keep the key: the first attempt may still be live
  if (s >= 400) return 'new';
  return 'reuse';
}

export function newHoldKey(): string {
  const c = (globalThis as {crypto?: {randomUUID?: () => string}}).crypto;
  const id = c?.randomUUID ? c.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`;
  return `mahan-hold-${id}`;
}

/** Error detail from the API (string or {code, message}) → code + Persian message. */
export function apiProblem(detail: unknown, fallback: string): {code?: string; message: string} {
  if (typeof detail === 'string') return {code: /کلید تکرار/.test(detail) ? 'IDEMPOTENCY_MISMATCH' : undefined, message: detail};
  if (Array.isArray(detail)) return {message: 'اطلاعات فرستاده‌شده را سرور نپذیرفت؛ فیلدها را بررسی کنید.'};
  if (detail && typeof detail === 'object') {
    const d = detail as {code?: unknown; message?: unknown};
    return {code: typeof d.code === 'string' ? d.code : undefined, message: typeof d.message === 'string' ? d.message : fallback};
  }
  return {message: fallback};
}

export const REASON_FA: Record<string, string> = {
  ok: 'فعال', disabled: 'خاموش (MAHAN_MODE=disabled)', invalid_mode: 'مقدار MAHAN_MODE نامعتبر است؛ اتصال بسته است.',
  missing_credentials: 'تنظیمات اتصال کامل نیست.', qaa_test_only: 'فقط برای کارشناس (محیط آزمایشی).', provider_error: 'پاسخ ماهان دریافت نشد.',
  airport_timezone_missing: 'منطقهٔ زمانی فرودگاه مبدأ یا مقصد در داده‌های مرجع ثبت نشده است.',
};
export const MODE_FA: Record<string, string> = {disabled: 'خاموش', qaa: 'آزمایشی (QAA)', live: 'عملیاتی (Live)'};
