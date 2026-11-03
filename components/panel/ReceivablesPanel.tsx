'use client';
/* Organization receivables: ageing by mandatory payment terms, FIFO settlements, payment recording. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Stats, Table, dateFa, errorOf, fa, money, useLoad} from './PanelKit';
import {FormFields, Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;
const METHODS: [string, string][] = [['bank', 'واریز بانکی'], ['cheque', 'چک'], ['cash', 'نقد'], ['offset', 'تهاتر']];

function Detail({id, close}: {id: string; close: () => void}) {
  const {state, reload, api} = useLoad<Row>(`/receivables/organizations/${id}`);
  const [terms, setTerms] = useState<Row | null>(null); const [pay, setPay] = useState<Row>({amount: null, paid_on: new Date().toISOString().slice(0, 10), method: 'bank', reference: '', note: ''});
  const [msg, setMsg] = useState<Msg>(null);
  return <Async state={state}>{d => {
    const t = terms ?? {payment_terms_days: d.terms_days ?? null, contact_name: d.contact_name ?? '', contact_mobile: d.contact_mobile ?? ''};
    async function saveTerms(e: FormEvent) {e.preventDefault(); setMsg(null); try {await api.put(`/receivables/organizations/${id}/terms`, {...t, contact_name: t.contact_name || null, contact_mobile: t.contact_mobile || null}); setTerms(null); setMsg({ok: true, text: 'مهلت پرداخت ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
    async function savePay(e: FormEvent) {e.preventDefault(); setMsg(null); try {await api.post(`/receivables/organizations/${id}/settlements`, {...pay, note: pay.note || null}); setPay({...pay, amount: null, reference: '', note: ''}); setMsg({ok: true, text: 'وصول ثبت شد و سند آن در دفتر صندوق خورد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
    return <Card title={d.name} action={<button className="pn-btn ghost" onClick={close}>بازگشت</button>}>
      {d.terms_missing && <p className="pn-note error">مهلت پرداخت این سازمان ثبت نشده؛ تا ثبت نشود سن مطالبات محاسبه نمی‌شود.</p>}
      <Stats items={[{label: 'جمع فاکتورها', value: money(d.invoiced, 'IRR')}, {label: 'وصول‌شده', value: money(d.settled, 'IRR')}, {label: 'مانده', value: money(d.outstanding, 'IRR')}, {label: 'معوق', value: money(d.overdue, 'IRR'), hint: d.oldest_overdue_days ? `قدیمی‌ترین ${fa(d.oldest_overdue_days)} روز` : undefined}]}/>
      {d.credit.length > 0 && <p className="pn-muted">اعتبار سازمانی: {d.credit.map((c: Row) => `سقف ${money(c.limit_amount, c.currency)}، قابل استفاده ${money(c.available, c.currency)}`).join(' — ')}</p>}
      <Note msg={msg}/>
      <form className="pn-form" onSubmit={saveTerms}><FormFields value={t} set={setTerms} fields={[{key: 'payment_terms_days', label: 'مهلت پرداخت (روز پس از صدور فاکتور)', type: 'number', required: true}, {key: 'contact_name', label: 'مسئول مالی سازمان'}, {key: 'contact_mobile', label: 'موبایل مسئول'}]}/><button className="pn-btn">ثبت مهلت</button></form>
      <h3>فاکتورها (تسویه به ترتیب قدیمی‌ترین)</h3>
      <Table rows={d.items} rowKey={(r: Row) => r.invoice_number} empty="فاکتوری برای رزروهای این سازمان صادر نشده است." cols={[
        {label: 'فاکتور', cell: (r: Row) => <span className="pn-ltr">{r.invoice_number}</span>}, {label: 'رزرو', cell: (r: Row) => <span className="pn-ltr">{r.booking_reference ?? '—'}</span>},
        {label: 'صدور', cell: (r: Row) => dateFa(r.issued_on)}, {label: 'سررسید', cell: (r: Row) => r.due_on ? dateFa(r.due_on) : '—'}, {label: 'مبلغ', cell: (r: Row) => money(r.total, 'IRR')},
        {label: 'وصول', cell: (r: Row) => money(r.paid, 'IRR')}, {label: 'مانده', cell: (r: Row) => money(r.open, 'IRR')},
        {label: 'وضعیت', cell: (r: Row) => r.open === 0 ? <span className="pn-badge ok">تسویه</span> : r.days_overdue > 0 ? <span className="pn-badge bad">{fa(r.days_overdue)} روز معوق</span> : <span className="pn-badge warn">باز</span>}]}/>
      <h3>ثبت وصول</h3>
      <form className="pn-form" onSubmit={savePay}><FormFields value={pay} set={setPay} fields={[{key: 'amount', label: 'مبلغ (ریال)', type: 'money', required: true}, {key: 'paid_on', label: 'تاریخ', type: 'date', required: true},
        {key: 'method', label: 'روش', type: 'select', options: METHODS}, {key: 'reference', label: 'شماره پیگیری / چک', required: true}, {key: 'note', label: 'توضیح'}]}/><button className="pn-btn">ثبت وصول (مدیر مالی)</button></form>
      <Table rows={d.settlements} rowKey={(r: Row) => r.id} empty="وصولی ثبت نشده است." cols={[{label: 'تاریخ', cell: (r: Row) => dateFa(r.paid_on)}, {label: 'مبلغ', cell: (r: Row) => money(r.amount, r.currency)},
        {label: 'روش', cell: (r: Row) => METHODS.find(x => x[0] === r.method)?.[1] ?? r.method}, {label: 'پیگیری', cell: (r: Row) => <span className="pn-ltr">{r.reference}</span>}, {label: 'سند', cell: (r: Row) => r.posted ? <span className="pn-badge ok">در دفتر</span> : '—'}]}/>
    </Card>;
  }}</Async>;
}

export function Receivables() {
  const {state} = useLoad<Row>('/receivables/organizations');
  const [open, setOpen] = useState<string | null>(null);
  if (open) return <Detail id={open} close={() => setOpen(null)}/>;
  return <Async state={state}>{d => <>
    <Stats items={[{label: 'کل مانده', value: money(d.outstanding, 'IRR')}, ...d.buckets.map((b: Row) => ({label: b.label, value: money(d.totals[b.key], 'IRR')}))]}/>
    {d.terms_missing > 0 && <p className="pn-note error">{fa(d.terms_missing)} سازمان مهلت پرداخت ندارند.</p>}
    <Card title="سازمان‌ها"><Table rows={d.items} rowKey={(r: Row) => r.organization_id} empty="سازمانی ثبت نشده است." cols={[
      {label: 'سازمان', cell: (r: Row) => r.name}, {label: 'مهلت', cell: (r: Row) => r.terms_missing ? <span className="pn-badge bad">ثبت نشده</span> : `${fa(r.terms_days)} روز`},
      {label: 'فاکتورها', cell: (r: Row) => money(r.invoiced, 'IRR')}, {label: 'مانده', cell: (r: Row) => money(r.outstanding, 'IRR')}, {label: 'معوق', cell: (r: Row) => r.overdue ? <span className="pn-badge bad">{money(r.overdue, 'IRR')}</span> : '—'},
      {label: '', cell: (r: Row) => <button className="pn-btn ghost" onClick={() => setOpen(r.organization_id)}>جزئیات</button>}]}/></Card>
  </>}</Async>;
}
