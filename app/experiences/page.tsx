import Link from 'next/link';
import { JourneyShell } from '../../components/journey/JourneyShell';
const leisureCategories:Array<[string,string,string,string]>=[
  ['استخر و ورزش','رزرو سانس استخر و مراکز ورزشی','◌','/pools-sports'],
  ['رستوران و کافه','رزرو میز و رستوران‌های معتبر','♨','/restaurants'],
  ['اماکن گردشگری و تفریحی','بلیت جاذبه‌ها و مراکز تفریحی','⌖','/attractions'],
  ['رویداد و تالار','بلیت رویداد و رزرو تالار','◇','/events-venues'],
];
export const metadata={title:'تجربه‌های مقصد',description:'تجربه‌ها و خدمات مقصد در اکوسیستم سفر کارن‌سیر',alternates:{canonical:'/experiences'},openGraph:{title:'تجربه‌های مقصد | کارن‌سیر',description:'جاذبه، رستوران، رویداد و تجربه‌های مقصد',url:'/experiences',type:'website'}};
export default function ExperiencesPage(){return <JourneyShell><main className="journey-main"><section className="dashboard container"><header className="dashboard-title"><div><span className="eyebrow">Destination Experiences</span><h1>تجربه‌های مقصد</h1><p>جاذبه، رستوران و رویدادها در کنار برنامه سفر؛ بدون نمایش موجودی جعلی.</p></div></header><div className="panel"><Link className="button primary" href="/destinations">انتخاب مقصد</Link><Link className="button secondary mr-2" href="/itineraries">افزودن به برنامه سفر</Link></div><div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:16,marginTop:24}}>{leisureCategories.map(([title,description,icon,href])=><Link href={href} key={href} style={{display:'block',padding:20,borderRadius:16,border:'1px solid var(--line)',background:'#fff'}}><i style={{fontSize:24}}>{icon}</i><h2 style={{margin:'10px 0 4px'}}>{title}</h2><p style={{margin:0,color:'var(--muted)',fontSize:14}}>{description}</p></Link>)}</div></section></main></JourneyShell>}
