import Link from 'next/link';
import {Suspense} from 'react';
import {HomeSearchExperience} from '../search/HomeSearchExperience';
import {HotelCatalog} from '../catalog/CatalogViews';
import {propertyTypes} from '../../lib/accommodation/catalog';
export function StayLanding(){return <main className="journey-main stay-marketplace"><header className="stay-intro"><span className="eyebrow">از هتل شهری تا خانه‌ای در دل طبیعت</span><h1>اقامت متناسب با سفرت را پیدا کن</h1><p>مقصد، تاریخ و تعداد مهمان را مشخص کن؛ اتاق، امکانات و شرایط هر اقامت را پیش از رزرو بررسی کن.</p></header><Suspense fallback={<p role="status">آماده‌سازی جست‌وجوی اقامت…</p>}><HomeSearchExperience defaultVertical="hotel"/></Suspense><section className="stay-discovery"><h2>چه جور اقامتی می‌خواهی؟</h2><div className="stay-type-links">{['hotel','villa','apartment','suite','ecolodge','cabin','traditional_house','pool_property','forest','coastal'].map(type=><Link key={type} href={'/villas?property_type='+type}>{propertyTypes[type]}</Link>)}</div></section><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><HotelCatalog/></Suspense></main>}
