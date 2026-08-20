/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV === 'development';
let apiOrigin = "'self'";
try { apiOrigin = new URL(process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').origin; } catch {}
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ''}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "worker-src 'self' blob:",
  ...(isDev ? [] : ['upgrade-insecure-requests']),
].join('; ');

const nextConfig = {
  output: 'standalone',
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'Content-Security-Policy', value: csp },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(self)' },
      ],
    }];
  },
};
export default nextConfig;
