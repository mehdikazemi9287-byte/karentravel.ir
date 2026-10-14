import Link from 'next/link';
import type { ReactNode } from 'react';
import { SupportDock } from './SupportDock';
export function JourneyShell({children,destination,disruption=false}:{children:ReactNode;destination?:string;disruption?:boolean}){return <div className="journey-page"><header className="journey-header"><Link className="journey-brand" href="/"><span>ک</span><b>کارن‌سیر<small>همراه سفر شما</small></b></Link><nav aria-label="ناوبری سفر"><Link href="/trips">سفرهای من</Link><Link href="/nearby">اطراف من</Link><Link href="/services">خدمات سفر</Link><Link href="/support">پشتیبانی</Link><Link href="/contact">تماس</Link></nav><Link className="journey-account" href="/account">حساب من</Link></header>{children}<SupportDock destination={destination} disruption={disruption}/></div>}
export function MockNotice({children='نسخه نمایشی — اطلاعات این بخش نمونه است.'}:{children?:ReactNode}){return <div className="journey-mock" role="note">● {children}</div>}
export { SupportDock };
