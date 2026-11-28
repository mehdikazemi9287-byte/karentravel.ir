import Link from 'next/link';
import { JourneyShell } from '../../components/journey/JourneyShell';
import { customerGroups } from '../../lib/customer-catalog';
import { HelpHero } from '../../components/customer/HelpCenter';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/services');

export default async function ServicesPage({searchParams}:{searchParams:Promise<{group?:string}>}){
  const {group}=await searchParams;
  const selected=group!==undefined&&/^[0-5]$/.test(group)?Number(group):null;
  const rows=selected===null?customerGroups:[customerGroups[selected]];
  return <JourneyShell><main className="journey-main hc-page">
    <HelpHero kicker="از برنامه‌ریزی تا پیگیری سفر" title={selected===null?'خدمات سفر':customerGroups[selected].title} lead="همه‌ی خدمات سفر کارن تراول در یک صفحه؛ خدمت موردنظرت را انتخاب کن یا برای راهنمایی تماس بگیر."/>
    <nav className="hc-pills" aria-label="دسته‌های خدمات"><Link href="/services" aria-current={selected===null?'page':undefined}>همه خدمات</Link>{customerGroups.map((g,i)=><Link key={g.title} href={'/services?group='+i} aria-current={selected===i?'page':undefined}>{g.title}</Link>)}</nav>
    <section className="hc-svc">{rows.map(g=><article key={g.title}><h2>{g.title}</h2><p>{g.copy}</p><ul>{g.items.map(([title,href])=><li key={href}><Link href={href}>{title} ←</Link></li>)}</ul></article>)}</section>
  </main></JourneyShell>;
}
