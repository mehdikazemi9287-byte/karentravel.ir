import Link from 'next/link';
import Image from 'next/image';
import { Shell } from '../page';
import { destinationGuides } from '../../lib/customer-catalog';
export default function DestinationsPage(){return <Shell><section className="container customer-page"><span className="eyebrow">ایده‌هایی برای سفر</span><h1>مقصد بعدی شما</h1><p>این راهنماها برای شناخت مقصد هستند؛ قیمت، موجودی یا بستهٔ قابل خرید نیستند.</p><div className="customer-grid">{destinationGuides.map(d=><Link className="panel customer-destination" key={d.slug} href={'/destinations/'+d.slug}><Image src={d.image} width={640} height={400} alt={d.name}/><h2>{d.name}</h2><p>{d.caption}</p><span>خواندن راهنمای مقصد ←</span></Link>)}</div></section></Shell>}
