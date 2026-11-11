/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV === 'development';
// Temporary, explicit opt-out for a no-TLS HTTP-only preview deploy: without this,
// the production CSP's upgrade-insecure-requests directive makes browsers silently
// rewrite every asset/API request to https://, which has no listener on an HTTP-only
// host and breaks the page entirely. Must never be set for a real HTTPS deployment.
const allowHttpPreview = process.env.ALLOW_HTTP_PREVIEW === '1';
// A path-mounted API ("https://karentravel.ir/api" or "http://<ip>/api") is called same-origin by browsers
// (lib/api/karenseir-client.ts resolveApiBase), so its configured origin — e.g. the bare server IP — is only
// added to the CSP for a bare API origin (dev :8000) or an HTTP preview, never for a real HTTPS build.
let apiOrigin = '';
try {
  const u = new URL(process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000');
  const pathMounted = u.pathname !== '/' && u.pathname !== '';
  if (!pathMounted || isDev || allowHttpPreview) apiOrigin = u.origin;
} catch {}
// The CSP itself is built per request with a nonce in proxy.ts (lib/csp.ts); these two build-time inputs are passed to it.

const nextConfig = {
  output: 'standalone',
  env: {KS_CSP_API_ORIGIN: apiOrigin, KS_CSP_HTTP_PREVIEW: allowHttpPreview ? '1' : ''},
  poweredByHeader: false,
  // The installable customer app lives at /app; its route folder is app/customer-app because a nested
  // app/app/ folder fails to compile inside the Docker image (WORKDIR /app -> /app/app/app/page.tsx).
  async rewrites() {
    return [
      {source: '/app', destination: '/customer-app'},
      {source: '/app/:path*', destination: '/customer-app/:path*'},
    ];
  },
  productionBrowserSourceMaps: false,
  async headers() {
    return [
      {
        source: '/',
        headers: [
          { key: 'Cache-Control', value: 'no-cache, must-revalidate' },
        ],
      },
      {
        source: '/:path*',
        headers: [
          // Content-Security-Policy: set once per request by proxy.ts (nonce), not here.
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(self), geolocation=(self)' },
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
          // No Strict-Transport-Security here: the TLS terminator (nginx, deploy/karenseir-https.sh) owns HSTS so it is
          // sent exactly once and its max-age can start short and be raised without a rebuild.
        ],
      },
    ];
  },
};
export default nextConfig;
