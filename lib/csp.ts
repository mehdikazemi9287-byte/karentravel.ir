/* Content-Security-Policy: the single source (security review M-3 follow-up). Used only by `proxy.ts`, which sets a
 * fresh nonce per request; next.config.mjs keeps the other security headers and no longer sends a CSP of its own.
 *
 * script-src: 'nonce-…' + 'strict-dynamic' — no 'unsafe-inline' for scripts. Next.js reads the nonce from the request's
 * CSP header and puts it on its own scripts; that only works for dynamically rendered pages, so the root layout opts
 * every page into dynamic rendering (app/layout.tsx, `connection()`).
 * style-src keeps 'unsafe-inline': React `style={…}` attributes cannot carry a nonce (styles cannot run code).
 *
 * CSP_MODE (runtime env of the web container):
 *   enforce (default)  — the nonce policy is enforced.
 *   report-only        — the previous policy (script 'unsafe-inline') stays enforced and the nonce policy is sent as
 *                        Content-Security-Policy-Report-Only, to watch a deployment before enforcing.
 */
export type CspInput = {nonce: string | null; isDev: boolean; httpPreview: boolean; apiOrigin: string};

export function buildCsp({nonce, isDev, httpPreview, apiOrigin}: CspInput): string {
  const apiSrc = apiOrigin ? ` ${apiOrigin}` : '';
  const script = nonce ? `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'` : "script-src 'self' 'unsafe-inline'";
  return [
    "default-src 'self'",
    `${script}${isDev ? " 'unsafe-eval'" : ''}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: https:${apiSrc}`,
    "font-src 'self' data:",
    `connect-src 'self'${apiSrc}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "worker-src 'self' blob:",
    ...(isDev || httpPreview ? [] : ['upgrade-insecure-requests']),
  ].join('; ');
}

export type CspMode = 'enforce' | 'report-only';
export function cspMode(value: string | undefined): CspMode {
  return (value || '').trim().toLowerCase() === 'report-only' ? 'report-only' : 'enforce';
}

/** 16 random bytes, base64 (Web Crypto: works in the Node.js proxy runtime and in tests). */
export function newNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let s = '';
  bytes.forEach(b => {s += String.fromCharCode(b);});
  return btoa(s);
}
