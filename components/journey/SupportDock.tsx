import Link from 'next/link';
import { supportPhone } from '../../lib/site-contact';
export function SupportDock({destination,disruption}:{destination?:string;disruption?:boolean}){return <aside className="support-dock" aria-label="کمک و پشتیبانی"><div><b>{destination?`برای سفر ${destination} راهنمایی می‌خواهید؟`:'برای سفرتان راهنمایی می‌خواهید؟'}</b>{disruption&&<span>پیش از تغییر یا لغو، شرایط رزرو را بررسی کنید.</span>}</div><nav><Link href="/support">راهنمای سفر</Link><a href={supportPhone.href}>تماس با پشتیبانی</a><Link href="/trips">پیگیری رزرو</Link></nav></aside>}
