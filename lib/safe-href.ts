// Only same-site relative paths ("/trips/123") may come from API data into an href.
// Blocks javascript:, data:, vbscript: and protocol-relative ("//evil.example") URLs.
export function safeHref(value: unknown, fallback = '#'): string {
  if (typeof value !== 'string') return fallback;
  const v = value.trim();
  if (!v.startsWith('/') || v.startsWith('//') || v.startsWith('/\\')) return fallback;
  if (/[\u0000-\u001f\u007f]/.test(v)) return fallback;
  return v;
}
