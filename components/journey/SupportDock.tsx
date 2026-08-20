'use client';

import Link from 'next/link';
import { useState } from 'react';

export function SupportDock({destination,disruption=false}:{destination?:string;disruption?:boolean}){
  const [open,setOpen]=useState(false);
  const title=destination?`برای سفر ${destination} کمکی لازم داری؟`:'کمکی لازم داری؟';

  return <aside className={`support-dock${open?' is-open':''}`} aria-label="دسترسی سریع به پشتیبانی">
    <button className="support-dock-trigger" type="button" aria-expanded={open} aria-controls="support-dock-panel" onClick={()=>setOpen(value=>!value)}>
      <span><b>{title}</b><small>{disruption?'تغییری در سفرت پیش آمده؟':'راهنمایی و پشتیبانی سفر'}</small></span>
      <strong>{open?'بستن':'کمک و پشتیبانی'}</strong>
    </button>
    <div className="support-dock-context">
      <b>{title}</b>
      <small>{disruption?'تغییری در سفرت پیش آمده؟':'دستیار هوشمند و کارشناس، دو مسیر جدا هستند.'}</small>
    </div>
    <div className="support-dock-actions" id="support-dock-panel">
      <Link href="/assistant?booking=book1" className="support-ai">✦ دستیار هوشمند</Link>
      <Link href="/support?channel=expert&trip=mock-shiraz-1405" className="support-expert">صحبت با کارشناس</Link>
      <Link href="/trips/mock-shiraz-1405" className="support-track">پیگیری رزرو</Link>
      <Link href="/manage-booking/book1" className="support-manage">تغییر و استرداد</Link>
      <Link href="/support?issue=urgent&trip=mock-shiraz-1405" className="urgent-help">مشکل در سفر</Link>
    </div>
  </aside>;
}
