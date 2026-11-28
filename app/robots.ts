import type { MetadataRoute } from 'next';
import { siteUrl } from '../lib/seo';
// Public pages are open to every crawler; only private areas (panels, account, checkout, internal search results) are disallowed.
export default function robots():MetadataRoute.Robots{return {rules:[{userAgent:'*',allow:['/'],disallow:['/search','/checkout/','/account','/admin','/agency','/backoffice','/employee','/finance','/manage-booking/','/organization','/pilot','/supplier','/trips/','/panel','/payments/','/contract/','/booking/','/customer-app','/app','/login','/register','/notifications','/saved-trips','/quotes','/v/']}],sitemap:`${siteUrl()}/sitemap.xml`,host:siteUrl()}}
