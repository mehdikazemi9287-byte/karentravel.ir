import {Suspense} from 'react';
import Link from 'next/link';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {HomeSearchExperience} from '../../components/search/HomeSearchExperience';
import {AirlineDirectory, AirportDirectory} from '../../components/catalog/CatalogViews';
export default function Page(){return <JourneyShell><main className="journey-main flight-entry"><h1>خرید بلیط هواپیما</h1><p>مبدأ، مقصد و تاریخ سفر را انتخاب کن تا پروازهای موجود را ببینی.</p><Suspense fallback={<p>در حال آماده‌سازی جست‌وجوی پرواز…</p>}><HomeSearchExperience/></Suspense><section className="flight-entry-steps"><article><b>پشتیبانی کارشناس</b><p>پیش و پس از خرید، کارشناس پشتیبانی همراه توست. <Link href="/support">تماس با پشتیبانی</Link></p></article><article><b>قوانین هر نرخ پیش از خرید</b><p>بار، کلاس و شرایط استرداد هر بلیت پیش از پرداخت نمایش داده می‌شود.</p></article><article><b>پیگیری در حساب من</b><p>وضعیت پرداخت و صدور بلیت را در <Link href="/trips">سفرهای من</Link> ببین.</p></article></section><AirlineDirectory/><AirportDirectory/></main></JourneyShell>}
