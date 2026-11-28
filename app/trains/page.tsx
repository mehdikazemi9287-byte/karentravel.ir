import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {HomeSearchExperience} from '../../components/search/HomeSearchExperience';
import {TrainLanding} from '../../components/catalog/CatalogViews';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/trains');
// Same landing structure as /flights: hero + search, then quick routes, perks, rail companies, FAQ.
export default function Page(){return <JourneyShell><main className="journey-main flight-entry fl-page">
  <section className="fl-hero fl-hero-train" aria-labelledby="tr-title"><span className="fl-kicker">قطار مسافری سراسر ایران</span><h1 id="tr-title">خرید بلیط قطار</h1><p>مبدأ، مقصد و تاریخ سفر را انتخاب کن تا قطارهای موجود را با ساعت حرکت، نوع واگن و قیمت ببینی.</p>
    <Suspense fallback={<p role="status">در حال آماده‌سازی جست‌وجوی قطار…</p>}><HomeSearchExperience defaultVertical="train"/></Suspense></section>
  <TrainLanding/></main></JourneyShell>}
