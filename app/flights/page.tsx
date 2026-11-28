import {OfflineRequest} from '../../components/customer/OfflineRequest';
import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {HomeSearchExperience} from '../../components/search/HomeSearchExperience';
import {AirlineDirectory, AirportDirectory, FlightLanding} from '../../components/catalog/CatalogViews';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/flights');

// Flight landing: hero + search, popular routes, airline strip, perks, FAQ. The full airline/airport
// directories (reference data) stay reachable but collapsed, instead of filling the page.
export default function Page() {
  return <JourneyShell><main className="journey-main flight-entry fl-page">
    <section className="fl-hero" aria-labelledby="fl-title">
      <span className="fl-kicker">پرواز داخلی و خارجی</span>
      <h1 id="fl-title">خرید بلیط هواپیما</h1>
      <p>مبدأ، مقصد و تاریخ سفر را انتخاب کن تا پروازهای موجود را با ساعت، بار مجاز و قوانین استرداد ببینی.</p>
      <Suspense fallback={<p>در حال آماده‌سازی جست‌وجوی پرواز…</p>}><HomeSearchExperience/></Suspense>
    </section>
    <FlightLanding/>
    <details className="fl-dir"><summary>فهرست کامل ایرلاین‌ها</summary><AirlineDirectory/></details>
    <details className="fl-dir"><summary>فهرست فرودگاه‌ها</summary><AirportDirectory/></details>
    <OfflineRequest service="بلیت هواپیما" trip="بلیت هواپیما"/>
  </main></JourneyShell>;
}
