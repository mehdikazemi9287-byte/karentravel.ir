'use client';
import Link from 'next/link';
import {Suspense,useState} from 'react';
import {HomeSearchExperience} from '../search/HomeSearchExperience';
import {HomeServicesHub,ReferenceHero,DestinationMosaic,ReferenceTrips,SmartCompanion,CompareBand,LocalExperiences,ReferenceOrganization,TrustSection,SearchHumanHelp,ReferenceFooter,FloatingAssistant} from './HistoricalPresentation';
export function MarketplaceHome(){const[menu,setMenu]=useState(false);return <div className="marketplace-home home-page recovery-home" data-product-slice="marketplace-1"><header className="mk-header"><div className="mk-wrap mk-header-inner"><Link className="mk-brand" href="/" aria-label="کارن‌سیر، صفحه اصلی"><span>ک</span><b>کارن‌سیر<small>سفر، اقامت و تجربه</small></b></Link><nav aria-label="ناوبری اصلی بازار سفر"><a href="#marketplace-services">خدمات سفر</a><a href="#discover">کشف مقصد</a><Link href="/assistant">دستیار هوشمند</Link><Link href="/organization">سفر سازمانی</Link><Link href="/trips">سفرهای من</Link><Link href="/support">پشتیبانی</Link></nav><Link className="mk-login" href="/login">ورود / ثبت‌نام</Link><button className="mk-menu" aria-label="فهرست خدمات سفر" aria-expanded={menu} onClick={()=>setMenu(!menu)}><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button></div>{menu&&<nav className="mk-mobile-menu" aria-label="ناوبری موبایل">{[['خدمات سفر','#marketplace-services'],['کشف مقصد','#discover'],['دستیار هوشمند','/assistant'],['سفر سازمانی','/organization'],['سفرهای من','/trips'],['پشتیبانی','/support']].map(([label,path])=><Link onClick={()=>setMenu(false)} key={path} href={path}>{label}</Link>)}</nav>}</header>
<main><ReferenceHero/>
<div className="ref-search-shell"><Suspense fallback={<p role="status">در حال آماده‌سازی جست‌وجوی سفر…</p>}><HomeSearchExperience/></Suspense><SearchHumanHelp/></div>
<div id="marketplace-services"><HomeServicesHub/></div>
<div id="discover"><DestinationMosaic/></div><ReferenceTrips/>
<SmartCompanion/>
<CompareBand/>
<LocalExperiences/>
<ReferenceOrganization/>
<TrustSection/></main>
<ReferenceFooter/><FloatingAssistant/></div>}

