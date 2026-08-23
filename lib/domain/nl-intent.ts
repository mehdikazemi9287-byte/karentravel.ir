// Deterministic, pattern-based Persian travel-intent extraction. Not an LLM;
// the same "deterministic natural-language structuring" approach already
// used server-side in _structured_search_intent. Never invents a field it
// didn't actually recognize -- callers should treat `missing` as the exact
// list of things to ask the user for, and leave everything else editable.

export type NLIntent = {
  raw: string;
  vertical?: string;
  origin?: string;
  destination?: string;
  adults?: number;
  children?: number;
  nights?: number;
  dateHint?: string;
  depart?: string;
  flexibility?: 'exact' | 'plus_minus_1' | 'plus_minus_3';
  budgetMax?: number;
  budgetHint?: 'economy';
  missing: string[];
};

const DIGIT_MAP: Record<string, string> = { '۰':'0','۱':'1','۲':'2','۳':'3','۴':'4','۵':'5','۶':'6','۷':'7','۸':'8','۹':'9','٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9' };
function normalizeText(text: string): string {
  return text.replace(/[۰-۹٠-٩]/g, (d) => DIGIT_MAP[d] ?? d).replace(/[يى]/g, 'ی').replace(/ك/g, 'ک').replace(/[‌\s]+/g, ' ').trim();
}

const CITY_ALIASES = ['تهران', 'شیراز', 'یزد', 'مشهد', 'اصفهان', 'کیش', 'قشم', 'کرج', 'تبریز', 'رشت', 'اهواز', 'ارومیه', 'استانبول', 'دبی', 'شمال', 'کاشان', 'همدان', 'بندرعباس'];
const NUMBER_WORDS: Record<string, number> = { 'یک':1,'دو':2,'سه':3,'چهار':4,'پنج':5,'شش':6,'هفت':7,'هشت':8,'نه':9,'ده':10 };
const VERTICAL_KEYWORDS: Array<[RegExp, string]> = [
  [/ویزا/, 'visa'], [/کروز/, 'cruise'], [/اجاره ?خودرو|ماشین/, 'car_rental'],
  [/ویلا|اقامتگاه/, 'vacation_rental'], [/هتل/, 'hotel'], [/تور/, 'tour'], [/قطار/, 'train'], [/پرواز|بلیط ?هواپیما/, 'flight'],
];
// Approximate Jalali-month -> Gregorian (day-of-year) start, for a friendly
// placeholder date only -- always shown as editable/approximate, never
// presented as an authoritative calendar conversion.
const JALALI_MONTH_START: Array<[string, number, number]> = [
  ['فروردین', 3, 21], ['اردیبهشت', 4, 21], ['خرداد', 5, 22], ['تیر', 6, 22], ['مرداد', 7, 23], ['شهریور', 8, 23],
  ['مهر', 9, 23], ['آبان', 10, 23], ['آذر', 11, 22], ['دی', 12, 22], ['بهمن', 1, 21], ['اسفند', 2, 20],
];

function nextOccurrence(month: number, day: number, today: Date): Date {
  let year = today.getFullYear();
  let d = new Date(year, month - 1, day);
  if (d.getTime() < today.setHours(0, 0, 0, 0)) d = new Date(year + 1, month - 1, day);
  return d;
}
function toIso(d: Date): string { return d.toISOString().slice(0, 10); }

export function parseTravelIntent(input: string, today: Date = new Date()): NLIntent {
  const text = normalizeText(input);
  const intent: NLIntent = { raw: input, missing: [] };

  for (const [re, vertical] of VERTICAL_KEYWORDS) { if (re.test(text)) { intent.vertical = vertical; break; } }

  const fromTo = text.match(/(?:از )?([آ-ی]+) (?:به|تا) ([آ-ی]+)/);
  if (fromTo && CITY_ALIASES.includes(fromTo[1]) && CITY_ALIASES.includes(fromTo[2])) { intent.origin = fromTo[1]; intent.destination = fromTo[2]; }
  else {
    const toOnly = text.match(/(?:به|تا) ([آ-ی]+)/);
    if (toOnly && CITY_ALIASES.includes(toOnly[1])) intent.destination = toOnly[1];
    else { for (const city of CITY_ALIASES) if (text.includes(city)) { intent.destination = city; break; } }
  }

  const paxNum = text.match(/(\d+) ?نفر/);
  const paxWord = text.match(/(یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده) ?نفر/);
  if (paxNum) intent.adults = parseInt(paxNum[1], 10);
  else if (paxWord) intent.adults = NUMBER_WORDS[paxWord[1]];
  else if (/من ?و ?همسرم|دو ?نفره/.test(text)) intent.adults = 2;
  const childMatch = text.match(/(\d+|یک|دو|سه) ?(بچه|کودک)/);
  if (childMatch) intent.children = /^\d+$/.test(childMatch[1]) ? parseInt(childMatch[1], 10) : NUMBER_WORDS[childMatch[1]];

  const nightMatch = text.match(/(\d+|یک|دو|سه|چهار|پنج|شش|هفت) ?شب/);
  const dayMatch = text.match(/(\d+|یک|دو|سه|چهار|پنج|شش|هفت) ?روز/);
  const toNum = (s: string) => (/^\d+$/.test(s) ? parseInt(s, 10) : NUMBER_WORDS[s]);
  if (nightMatch) intent.nights = toNum(nightMatch[1]);
  else if (dayMatch) intent.nights = Math.max(1, toNum(dayMatch[1]) - 1);

  const budgetMatch = text.match(/تا ?(\d+) ?میلیون/);
  if (budgetMatch) intent.budgetMax = parseInt(budgetMatch[1], 10) * 1_000_000;
  if (/ارزون|اقتصادی/.test(text)) intent.budgetHint = 'economy';

  if (/آخر ?هفته/.test(text)) {
    intent.dateHint = 'آخر هفته';
    const day = today.getDay();
    const untilFriday = (5 - day + 7) % 7 || 7;
    intent.depart = toIso(new Date(today.getFullYear(), today.getMonth(), today.getDate() + untilFriday));
    intent.flexibility = 'plus_minus_1';
  } else if (/فردا/.test(text)) {
    intent.dateHint = 'فردا';
    intent.depart = toIso(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1));
  } else if (/هفته ?بعد/.test(text)) {
    intent.dateHint = 'هفته بعد';
    intent.depart = toIso(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7));
    intent.flexibility = 'plus_minus_3';
  } else {
    const monthHit = JALALI_MONTH_START.find(([name]) => text.includes(name));
    if (monthHit) {
      const [, month, startDay] = monthHit;
      const isEnd = /آخر/.test(text);
      const base = nextOccurrence(month, startDay, new Date(today));
      intent.depart = toIso(isEnd ? new Date(base.getFullYear(), base.getMonth(), base.getDate() + 25) : base);
      intent.dateHint = isEnd ? `آخر ${monthHit[0]}` : monthHit[0];
      intent.flexibility = 'plus_minus_3';
    }
  }
  if (/فرقی ?نداره|انعطاف/.test(text)) intent.flexibility = 'plus_minus_3';

  if (!intent.destination) intent.missing.push('destination');
  if (!intent.vertical) intent.vertical = intent.origin && intent.destination ? 'flight' : intent.destination ? 'hotel' : undefined;
  if (!intent.vertical) intent.missing.push('vertical');

  return intent;
}
