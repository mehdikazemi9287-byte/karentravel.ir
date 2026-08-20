import Link from 'next/link';
import type { ReactNode } from 'react';
import { SupportDock } from './SupportDock';
export function JourneyShell({children,destination='شیراز',disruption=true}:{children:ReactNode;destination?:string;disruption?:boolean}){return <div className="journey-page"><header className="journey-header"><Link className="journey-brand" href="/"><span>ک</span><b>کارن‌سیر<small>همراه سفر شما</small></b></Link><nav aria-label="ناوبری سفر"><Link href="/trips">سفرهای من</Link><Link href="/nearby?trip=mock-shiraz-1405">اطراف من</Link><Link href="/services?destination=shiraz">خدمات سفر</Link><Link href="/support?trip=mock-shiraz-1405">پشتیبانی</Link></nav><Link className="journey-account" href="/employee">حساب من</Link></header>{children}<SupportDock destination={destination} disruption={disruption}/></div>}
export function MockNotice({children='نسخه نمایشی — اطلاعات این بخش نمونه است.'}:{children?:ReactNode}){return <div className="journey-mock" role="note">● {children}</div>}
export { SupportDock };
