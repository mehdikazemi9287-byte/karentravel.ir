'use client';
/* SMS campaigns: audience from sales-desk cases or loyalty levels, opt-outs, honest delivery status. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Table, errorOf, fa, useLoad} from './PanelKit';
import {FormFields, Note, Tabs, type Opt, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;
const STAGES: Opt = [['', 'همه'], ['new', 'جدید'], ['contacted', 'تماس گرفته شد'], ['quoted', 'پیش‌فاکتور'], ['awaiting_payment', 'منتظر پرداخت'], ['paid', 'پرداخت شد'], ['issued', 'صادر شد'], ['travelled', 'سفر انجام شد'], ['lost', 'منصرف']];
const CHANNELS: Opt = [['', 'همه'], ['web_form', 'فرم سایت'], ['whatsapp', 'واتس‌اپ'], ['bale', 'بله'], ['phone', 'تلفن'], ['instagram', 'اینستاگرام'], ['campaign', 'کمپین'], ['referral', 'معرفی'], ['walk_in', 'حضوری']];
const STATUS: Record<string, [string, string]> = {draft: ['پیش‌نویس', 'warn'], sending: ['در حال ارسال', 'warn'], sent: ['ارسال شد', 'ok'], waiting_for_provider: ['منتظر اتصال سرویس پیامک', 'bad'], cancelled: ['لغو شد', ''], failed: ['ارسال ناموفق', 'bad']};

function Provider() {
  const {state} = useLoad<Row>('/sms-campaigns/provider');
  return <Async state={state}>{p => p.connected ? <p className="pn-note">سرویس پیامک وصل است.</p> :
    <p className="pn-note error">سرویس پیامک هنوز وصل نیست؛ کمپین ساخته و مخاطبانش ثبت می‌شوند ولی پیامی فرستاده نمی‌شود تا سرویس وصل شود.</p>}</Async>;
}

function Campaigns() {
  const {state, reload, api} = useLoad<{items: Row[]}>('/sms-campaigns');
  const [v, setV] = useState<Row>({title: '', body: '', source: 'sales_desk', stage: '', channel: '', level_key: ''});
  const [count, setCount] = useState<number | null>(null); const [msg, setMsg] = useState<Msg>(null);
  const audience = () => v.source === 'loyalty' ? {source: 'loyalty', level_key: v.level_key || null} : {source: 'sales_desk', stages: v.stage ? [v.stage] : [], channels: v.channel ? [v.channel] : []};
  async function create(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    try {await api.post('/sms-campaigns', {title: v.title, body: v.body, audience: audience()}); setMsg({ok: true, text: 'کمپین ساخته شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  async function act(path: string, ok: string) {setMsg(null); try {const r = await api.post<Row>(path, {}); setMsg({ok: true, text: `${ok} — گیرنده ${fa(r.recipients)}، ارسال‌شده ${fa(r.delivered)}، منتظر سرویس ${fa(r.blocked)}`}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  const len = (v.body || '').length + 6;
  return <>
    <Provider/>
    <Card title="کمپین جدید"><form className="pn-form" onSubmit={create}>
      <FormFields value={v} set={setV} fields={[{key: 'title', label: 'عنوان (داخلی)', required: true},
        {key: 'source', label: 'مخاطبان', type: 'select', options: [['sales_desk', 'مشتریان میز فروش'], ['loyalty', 'اعضای حلقه‌ی همسفران']]},
        ...(v.source === 'loyalty' ? [{key: 'level_key', label: 'کلید سطح (خالی = همه)'}] : [{key: 'stage', label: 'مرحله', type: 'select' as const, options: STAGES}, {key: 'channel', label: 'کانال', type: 'select' as const, options: CHANNELS}]),
        {key: 'body', label: 'متن پیام', type: 'textarea', wide: true, required: true, hint: `${fa(len)} نویسه، ${fa(Math.max(1, Math.ceil(len / 67)))} پیامک؛ «لغو۱۱» خودکار به انتها اضافه می‌شود`}]}/>
      <button type="button" className="pn-btn ghost" onClick={async () => {try {setCount((await api.post<Row>('/sms-campaigns/preview', audience())).count);} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}}>شمارش مخاطبان</button>
      {count !== null && <span className="pn-muted">{fa(count)} مخاطب (بدون شماره‌های لغو اشتراک)</span>}
      <button className="pn-btn">ساخت کمپین</button></form><Note msg={msg}/></Card>
    <Card title="کمپین‌ها"><Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="هنوز کمپینی ساخته نشده است." cols={[
      {label: 'عنوان', cell: r => r.title}, {label: 'وضعیت', cell: r => <span className={`pn-badge ${STATUS[r.status]?.[1] ?? ''}`}>{STATUS[r.status]?.[0] ?? r.status}</span>},
      {label: 'گیرنده', cell: r => fa(r.recipients)}, {label: 'ارسال‌شده', cell: r => fa(r.delivered)}, {label: 'منتظر سرویس', cell: r => fa(r.blocked)}, {label: 'پیامک', cell: r => fa(r.parts)},
      {label: '', cell: r => ['draft', 'waiting_for_provider', 'failed'].includes(r.status) ? <span style={{display: 'flex', gap: 6}}><button className="pn-btn" onClick={() => act(`/sms-campaigns/${r.id}/send`, 'ارسال انجام شد')}>{r.status === 'draft' ? 'ارسال' : 'تلاش دوباره'}</button><button className="pn-btn ghost" onClick={() => act(`/sms-campaigns/${r.id}/cancel`, 'لغو شد')}>لغو</button></span> : null}]}/>}</Async></Card>
  </>;
}

function OptOuts() {
  const {state, reload, api} = useLoad<{items: Row[]}>('/sms-campaigns/opt-outs');
  const [v, setV] = useState<Row>({mobile: ''}); const [msg, setMsg] = useState<Msg>(null);
  return <Card title="لغو اشتراک پیامک"><form className="pn-form" onSubmit={async e => {e.preventDefault(); setMsg(null); try {await api.post('/sms-campaigns/opt-outs', v); setV({mobile: ''}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}}>
    <FormFields value={v} set={setV} fields={[{key: 'mobile', label: 'موبایل', required: true}]}/><button className="pn-btn">افزودن</button></form><Note msg={msg}/>
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.mobile} empty="فهرست خالی است." cols={[{label: 'موبایل', cell: r => <span className="pn-ltr">{r.mobile}</span>}, {label: 'منبع', cell: r => r.source === 'manual' ? 'دستی' : r.source}]}/>}</Async></Card>;
}

export function SmsCampaigns() {return <Tabs tabs={[['کمپین‌ها', <Campaigns key="c"/>], ['لغو اشتراک', <OptOuts key="o"/>]]}/>;}
