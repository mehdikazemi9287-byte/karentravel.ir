import type {Metadata} from 'next';
import {Suspense} from 'react';
import Link from 'next/link';
import {JourneyShell} from '../../../../components/journey/JourneyShell';
import {TourCatalog} from '../../../../components/catalog/CatalogViews';
import {catalogSeo} from '../../../../lib/catalog-seo';
export async function generateMetadata({params}:{params:Promise<{place:string}>}): Promise<Metadata> {const {place}=await params;const seo=await catalogSeo(`/catalog/places/${encodeURIComponent(place)}`);return {title:seo?seo.title.replace('سفر به','تورهای').replace('راهنمای مقصد','برنامهٔ تور'):'تورهای مقصد | کارن‌سیر'}}
export default async function Page({params}:{params:Promise<{place:string}>}){const {place}=await params;return <JourneyShell><main className="journey-main"><nav className="cat-crumbs" aria-label="مسیر"><Link href="/tours">تورها</Link><Link href="/tours/search">همهٔ مقصدها</Link><Link href={`/destinations/${place}`}>راهنمای این مقصد</Link></nav><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><TourCatalog title="تورهای این مقصد" presetDestination={place}/></Suspense></main></JourneyShell>}
