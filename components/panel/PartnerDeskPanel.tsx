'use client';
/* Agents' view of requests sent to partners. ShahrShad requests are confirmed by an agent here; Padvira and Gift Asan
   requests are already in the partner's own panel and their status comes from there. */
import {useState} from 'react';
import {Async, Card, Table, dateFa, errorOf, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';

function Act({r, done}: {r: Row; done: (m: {ok: boolean; text: string}) => void}) {
  const {api} = useLoad<Row>(null); const [note, setNote] = useState('');
  const go = async (status: string) => {try {await api.post(`/partner-desk/requests/${r.id}/status`, {status, public_note: note || null}); done({ok: true, text: 'وضعیت ثبت شد و مشتری در حسابش می‌بیند.'});} catch (x) {done({ok: false, text: errorOf(x).message});}};
  return <span className="tr-actions"><input aria-label="پیام به مشتری" placeholder="پیام به مشتری" value={note} onChange={e => setNote(e.target.value)}/>
    <button className="pn-btn ghost" type="button" onClick={() => void go('review')}>در حال بررسی</button><button className="pn-btn" type="button" onClick={() => void go('done')}>انجام شد</button><button className="pn-btn ghost" type="button" onClick={() => void go('rejected')}>ممکن نیست</button></span>;
}

export function PartnerDesk() {
  const [partner, setPartner] = useState('shahrshad');
  const {state, reload} = useLoad<{items: Row[]}>(`/partner-desk/requests?partner=${partner}`);
  const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  return <Card title="درخواست‌های خدمات همکار" action={<select aria-label="مجموعه" value={partner} onChange={e => setPartner(e.target.value)}><option value="shahrshad">شهرشاد (تأیید با کارشناس)</option><option value="padvira">پادویرا</option><option value="giftasan">گیفت آسان</option></select>}>
    <Note msg={msg}/>
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="درخواستی نیست." cols={[
      {label: 'تاریخ', cell: r => dateFa(r.created_at)}, {label: 'کد', cell: r => <span dir="ltr">{r.reference}</span>}, {label: 'خدمت', cell: r => r.service},
      {label: 'جزئیات', cell: r => r.summary}, {label: 'تماس', cell: r => <span dir="ltr">{r.contact}</span>}, {label: 'وضعیت', cell: r => r.status_fa},
      {label: '', cell: r => r.manual && !['done', 'rejected'].includes(r.status) ? <Act r={r} done={m => {setMsg(m); reload();}}/> : null}]}/>}</Async>
  </Card>;
}
