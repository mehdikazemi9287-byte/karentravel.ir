/* Pure URL builders for search and sign-in links (unit-tested in tests/unit/search-links.cjs). */
import type {NLIntent} from './domain/nl-intent';

/** «ورود / ثبت‌نام» that returns to this page after sign-in. /login honours only an in-app path (safeRedirectTarget). */
export function loginHref(path: string, search = ''): string {
  const here = (path || '/') + (search && search !== '?' ? (search.startsWith('?') ? search : '?' + search) : '');
  return '/login?redirect=' + encodeURIComponent(here);
}

/** The smart assistant's «جست‌وجو»: the same results page as the form (trains: the train request form). The sentence
 *  carries no return date, so a flight is one-way; a stay with «N شب» gets its check-out date. */
export function nlSearchHref(intent: NLIntent, fallback: {depart: string; adults: number}): string {
  const vertical = intent.vertical ?? 'hotel';
  const depart = intent.depart ?? fallback.depart;
  const params = new URLSearchParams({vertical, origin: intent.origin ?? '', destination: intent.destination ?? '', depart,
    flexibility: intent.flexibility ?? 'exact', adults: String(intent.adults ?? fallback.adults), children: String(intent.children ?? 0),
    infants: '0', rooms: '1', cabin: 'economy', sort: 'recommended'});
  if (vertical === 'flight') params.set('trip_type', 'one_way');
  if ((vertical === 'hotel' || vertical === 'vacation_rental') && depart && intent.nights && intent.nights > 0) {
    const out = new Date(`${depart}T00:00:00Z`); out.setUTCDate(out.getUTCDate() + intent.nights); params.set('return', out.toISOString().slice(0, 10));
  }
  if (intent.budgetMax) params.set('max_price', String(intent.budgetMax));
  return (vertical === 'train' ? '/trains/request?' : '/search/results?') + params.toString();
}
