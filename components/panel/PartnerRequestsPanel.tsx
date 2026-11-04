'use client';
/* The customer's requests to Padvira and Gift Asan, with the partner's current status and public reply. */
import Link from 'next/link';
import {Async, Card, Empty, dateFa, useLoad} from './PanelKit';
import type {Row} from './CommercePanel';

export function MyPartnerRequests() {
  const {state} = useLoad<{items: Row[]}>('/me/partner-requests');
  return <Card title="درخواست‌های پادویرا و گیفت آسان">
    <Async state={state}>{d => d.items.length === 0 ? <Empty>هنوز درخواستی ثبت نکرده‌اید. <Link href="/experiences">تجربه‌ها و سوغات</Link></Empty> :
      <div className="tr-list">{d.items.map(r => <article key={r.id} className="tr-item">
        <header><b>{r.partner_fa} · {r.service}</b><span className={`pn-badge ${['done', 'completed'].includes(r.status) ? 'ok' : ['rejected', 'cancelled'].includes(r.status) ? 'bad' : 'warn'}`}>{r.status_fa}</span></header>
        <p className="pn-muted">{dateFa(r.created_at)} · کد <span dir="ltr">{r.reference}</span></p>
        <p>{r.summary}</p>
        {r.public_note && <p className="pn-note">پاسخ {r.partner_fa}: {r.public_note}</p>}
        <a href={r.track_url} target="_blank" rel="noreferrer">پیگیری در سایت {r.partner_fa} ←</a>
      </article>)}</div>}</Async>
  </Card>;
}
