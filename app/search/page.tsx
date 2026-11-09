import {redirect} from 'next/navigation';

/* /search has no page of its own: older links (the customer app's "جستجو" tab, bookmarks) land on the unified results view.
   Any query string is carried over so a shared search link keeps working. */
export default async function SearchIndex({searchParams}: {searchParams: Promise<Record<string, string | string[] | undefined>>}) {
  const params = await searchParams;
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) for (const v of Array.isArray(value) ? value : value === undefined ? [] : [value]) qs.append(key, v);
  const query = qs.toString();
  redirect(query ? `/search/results?${query}` : '/search/results');
}
