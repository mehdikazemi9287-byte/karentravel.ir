/* SEO helpers for the public site (group SEO baseline, docs/group-knowledge/SEO_BASELINE.md).
   One place for the site origin, per-page metadata (title + description + canonical + Open Graph) and JSON-LD. */
import type {Metadata} from 'next';

export const PRODUCTION_ORIGIN = 'https://karentravel.ir';
export const SITE_NAME = 'کارن تراول';

/** The public origin used in robots.txt, sitemap.xml, canonical and JSON-LD.
 *  NEXT_PUBLIC_SITE_URL is used only when it is an https domain: on 2026-11-28 it was the bare server IP
 *  (http://188.121.123.218) and every canonical pointed there. An http:// or IP value falls back to the real domain. */
export function siteUrl(): string {
  const raw = (process.env.NEXT_PUBLIC_SITE_URL || '').trim().replace(/\/+$/, '');
  try {
    const u = new URL(raw);
    if (u.protocol === 'https:' && !/^\d{1,3}(\.\d{1,3}){3}$/.test(u.hostname) && u.hostname !== 'localhost') return u.origin;
  } catch {}
  return PRODUCTION_ORIGIN;
}

/** Absolute URL on the public origin for a site path ("/tours" → "https://karentravel.ir/tours"). */
export const absoluteUrl = (path: string) => siteUrl() + (path === '/' ? '' : path.startsWith('/') ? path : `/${path}`);

/** Metadata for one public page: unique title (the root template adds « | کارن تراول»), 120–160 char description,
 *  canonical without query string, and Open Graph. `absoluteTitle` skips the template (used for the homepage). */
export function pageMetadata({title, description, path, absoluteTitle = false, noindex = false, image}: {
  title: string; description: string; path: string; absoluteTitle?: boolean; noindex?: boolean; image?: string;
}): Metadata {
  const fullTitle = absoluteTitle ? title : `${title} | ${SITE_NAME}`;
  return {
    title: absoluteTitle ? {absolute: title} : title,
    description,
    alternates: {canonical: path.split('?')[0] || '/'},
    openGraph: {title: fullTitle, description, url: path.split('?')[0] || '/', siteName: SITE_NAME, locale: 'fa_IR', type: 'website', ...(image ? {images: [{url: image}]} : {})},
    ...(noindex ? {robots: {index: false, follow: true}} : {}),
  };
}

/** schema.org TravelAgency for the business. Only facts that are in the code: name, domain, logo, support phone. */
export function organizationLd(phone?: string) {
  return {
    '@context': 'https://schema.org', '@type': 'TravelAgency', '@id': `${siteUrl()}/#organization`,
    name: SITE_NAME, alternateName: 'Karen Travel', url: siteUrl(), logo: `${siteUrl()}/images/approved-figma/imgComponentLogoMark.svg`,
    ...(phone ? {telephone: phone, contactPoint: {'@type': 'ContactPoint', telephone: phone, contactType: 'customer support', availableLanguage: 'fa'}} : {}),
  };
}

export function websiteLd() {
  return {'@context': 'https://schema.org', '@type': 'WebSite', '@id': `${siteUrl()}/#website`, name: SITE_NAME, url: siteUrl(), inLanguage: 'fa-IR', publisher: {'@id': `${siteUrl()}/#organization`}};
}

/** BreadcrumbList from [name, path] pairs, home first. */
export function breadcrumbLd(items: [string, string][]) {
  return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', itemListElement: items.map(([name, path], i) => ({'@type': 'ListItem', position: i + 1, name, item: absoluteUrl(path)}))};
}

/** schema.org TouristTrip for a tour programme (name/description from the catalogue; no invented price or dates). */
export function touristTripLd({name, description, path}: {name: string; description: string; path: string}) {
  return {'@context': 'https://schema.org', '@type': 'TouristTrip', name, description, url: absoluteUrl(path), provider: {'@id': `${siteUrl()}/#organization`}};
}
