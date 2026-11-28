/* Server-side read of a themed tour collection, so the tour list is in the HTML (crawlers, no-JS) and the browser does
   not wait for a second request. `null` = API not reachable: the page falls back to loading in the browser as before. */
import type {CollectionKey, CollectionData} from '../components/catalog/TourCollections';

const serverBase = () => (process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const tenant = () => process.env.NEXT_PUBLIC_TENANT_SLUG || 'aftab-bank';

export async function serverTourCollection(collection: CollectionKey): Promise<CollectionData | null> {
  try {
    const r = await fetch(`${serverBase()}/public/tenants/${encodeURIComponent(tenant())}/tour-collections/${collection}`, {signal: AbortSignal.timeout(3000), next: {revalidate: 300}});
    return r.ok ? ((await r.json()) as CollectionData) : null;
  } catch {return null;}
}
