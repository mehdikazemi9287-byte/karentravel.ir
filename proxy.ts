import {NextResponse, type NextRequest} from 'next/server';
import {buildCsp, cspMode, newNonce} from './lib/csp';

/* Per-request nonce CSP (see lib/csp.ts). Only the CSP is set here; the other security headers stay in next.config.mjs. */
export function proxy(request: NextRequest) {
  const nonce = newNonce();
  const base = {isDev: process.env.NODE_ENV === 'development', httpPreview: process.env.KS_CSP_HTTP_PREVIEW === '1', apiOrigin: process.env.KS_CSP_API_ORIGIN || ''};
  const strict = buildCsp({...base, nonce});
  const mode = cspMode(process.env.CSP_MODE);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-nonce', nonce);
  // Next.js takes the nonce for its own scripts from this request header (both modes, so report-only shows real violations only).
  requestHeaders.set('Content-Security-Policy', strict);
  const response = NextResponse.next({request: {headers: requestHeaders}});
  if (mode === 'report-only') {
    response.headers.set('Content-Security-Policy', buildCsp({...base, nonce: null}));
    response.headers.set('Content-Security-Policy-Report-Only', strict);
  } else {
    response.headers.set('Content-Security-Policy', strict);
  }
  return response;
}

export const config = {
  matcher: [
    {
      source: '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|css|js|map|txt|xml|json|webmanifest)$).*)',
      missing: [
        {type: 'header', key: 'next-router-prefetch'},
        {type: 'header', key: 'purpose', value: 'prefetch'},
      ],
    },
  ],
};
