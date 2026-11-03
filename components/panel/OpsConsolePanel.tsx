'use client';
/* Ops dashboard (پیشخوان عملیات) and contract file (پرونده‌ی قرارداد). Every number comes from /ops/* — nothing estimated. */
import Link from 'next/link';
import {useState, type FormEvent} from 'react';
import {Async, Card, Stats, Table, dateFa, errorOf, fa, money, serviceFa, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;
const CHANNEL_FA: Record<string, string> = {web: 'سایت', phone: 'تلفن', whatsapp: 'واتس‌اپ', bale: 'بله', telegram: 'تلگرام', instagram: 'اینستاگرام', walk_in: 'حضوری', referral: 'معرفی', pbx: 'سانترال', sms: 'پیامک', email: 'ایمیل', agency: 'همکار', organization: 'سازمانی'};
const timeFa = (iso?: string | null) => iso ? new Date(iso).toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tehran'}) : '—';
const dayFa = (d: string) => new Date(d + 'T12:00:00+03:30').toLocaleDateString('fa-IR', {month: 'short', day: 'numeric'});

/* 30-day bars: one series (single hue, no legend), 4px rounded tops on the baseline, 2px gaps, hover/focus tooltip, table fallback. */
function DailyBars({data}: {data: {day: string; count: number; value: number}[]}) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const max = Math.max(1, ...data.map(d => d.count));
  const W = 600, H = 160, gap = 2, bw = W / data.length - gap;
  const h = hover === null ? null : data[hover];
  if (asTable) return <>
    <button className="pn-btn ghost" onClick={() => setAsTable(false)}>نمایش نمودار</button>
    <Table rows={[...data].reverse()} rowKey={r => r.day} empty="—" cols={[{label: 'روز', cell: r => dayFa(r.day)}, {label: 'قرارداد', cell: r => fa(r.count)}, {label: 'ارزش', cell: r => money(r.value, 'IRR')}]}/>
  </>;
  return <div className="ops-chart">
    <div className="ops-chart-head"><span className="pn-muted">{h ? `${dayFa(h.day)}: ${fa(h.count)} قرارداد، ${money(h.value, 'IRR')}` : 'تعداد قراردادهای تأییدشده در هر روز (به وقت تهران)'}</span>
      <button className="pn-btn ghost" onClick={() => setAsTable(true)}>نمایش جدول</button></div>
    <svg viewBox={`0 0 ${W} ${H + 22}`} role="img" aria-label="نمودار ۳۰ روز قراردادهای تأییدشده" style={{direction: 'ltr'}} onMouseLeave={() => setHover(null)}>
      <line x1="0" x2={W} y1={H} y2={H} stroke="var(--pn-line)"/>
      {data.map((d, i) => {
        const x = i * (bw + gap), bh = d.count ? Math.max(4, (d.count / max) * (H - 8)) : 0;
        return <g key={d.day} tabIndex={0} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} aria-label={`${dayFa(d.day)}: ${fa(d.count)}`}>
          <rect x={x} y={0} width={bw + gap} height={H} fill="transparent"/>
          {bh > 0 && <path d={`M${x},${H} V${H - bh + 4} q0,-4 4,-4 h${bw - 8} q4,0 4,4 V${H} Z`} fill="#7a3f7e" opacity={hover === null || hover === i ? 1 : 0.45}/>}
          {(i === data.length - 1 || (data.length - 1 - i) % 7 === 0) && <text x={x + bw / 2} y={H + 16} textAnchor="middle" fontSize="13" fill="var(--pn-muted)">{dayFa(d.day)}</text>}
        </g>;
      })}
    </svg>
  </div>;
}

export function OpsDashboard() {
  const {state, reload} = useLoad<Row>('/ops/dashboard');
  return <Async state={state}>{d => <>
    <div className="ops-row"><span className="pn-muted">امروز {dateFa(d.today)} — به‌روز شده ساعت {timeFa(d.generated_at)}</span><button className="pn-btn ghost" onClick={reload}>به‌روزرسانی</button></div>
    <Stats items={d.kpis.map((k: Row) => ({label: k.label, value: k.unit === 'IRR' ? money(k.value, 'IRR') : fa(k.value), hint: k.hint?.replace(/\d/g, (x: string) => '۰۱۲۳۴۵۶۷۸۹'[Number(x)])}))}/>
    {d.alerts.length > 0 && <Card title="هشدارهای داده">
      <ul className="ops-alerts">{d.alerts.map((a: Row) => <li key={a.key} className={`pn-note ${a.level === 'bad' ? 'error' : ''}`}><b>{a.level === 'bad' ? '⛔' : '⚠️'} {fa(a.count)}</b> {a.label}</li>)}</ul></Card>}
    <div className="ops-grid">
      <Card title="کارهای در انتظار"><ul className="ops-tasks">{d.tasks.map((t: Row) => <li key={t.key}><Link href={t.href}>{t.label}</Link><span className={`pn-badge ${t.count ? 'warn' : 'ok'}`}>{fa(t.count)}</span></li>)}</ul></Card>
      <Card title="۳۰ روز اخیر"><DailyBars data={d.chart}/></Card>
    </div>
    <Card title="آخرین قراردادها" action={<Link className="pn-btn ghost" href="/admin/contracts">همه‌ی قراردادها</Link>}>
      <Table rows={d.latest} rowKey={(r: Row) => r.id} empty="هنوز قراردادی ثبت نشده است." cols={[
        {label: 'شماره', cell: (r: Row) => <Link className="pn-ltr" href={`/admin/contracts?id=${r.id}`}>{r.booking_reference ?? r.id.slice(0, 8)}</Link>},
        {label: 'خدمت', cell: (r: Row) => serviceFa(r.service_type)}, {label: 'مشتری', cell: (r: Row) => r.customer ?? '—'},
        {label: 'مبلغ', cell: (r: Row) => money(r.amount, r.currency)}, {label: 'وضعیت', cell: (r: Row) => <span className="pn-badge">{r.status_fa}</span>}, {label: 'ثبت', cell: (r: Row) => timeFa(r.created_at)}]}/>
    </Card>
    <div className="ops-grid">
      <Card title="پروازهای امروز (موجودی خودمان)"><Table rows={d.flights} rowKey={(r: Row) => r.id} empty="امروز پروازی از موجودی خودمان نیست." cols={[
        {label: 'پرواز', cell: (r: Row) => <span className="pn-ltr">{r.flight} {r.route}</span>}, {label: 'حرکت', cell: (r: Row) => timeFa(r.departure_at)},
        {label: 'ظرفیت', cell: (r: Row) => fa(r.capacity)}, {label: 'فروخته', cell: (r: Row) => r.sold === null ? '—' : fa(r.sold)},
        {label: 'سهمیه', cell: (r: Row) => fa(r.held)}, {label: 'لیست', cell: (r: Row) => r.list_sent ? <span className="pn-badge ok">ارسال شد</span> : <span className="pn-badge warn">ارسال نشده</span>}]}/></Card>
      <Card title="تیم و کانال‌ها">
        <Table rows={d.team.agents} rowKey={(r: Row) => String(r.user_id)} empty="کارشناس فروشی تعریف نشده است." cols={[
          {label: 'کارشناس', cell: (r: Row) => r.name ?? '—'}, {label: 'حضور', cell: (r: Row) => r.present ? <span className="pn-badge ok">حاضر</span> : <span className="pn-badge">غایب</span>}, {label: 'پرونده‌ی باز', cell: (r: Row) => fa(r.open_cases)}]}/>
        <p className="pn-muted">درخواست‌ها در ۳۰ روز: {d.team.channels.length ? d.team.channels.map((c: Row) => `${CHANNEL_FA[c.channel] ?? c.channel} ${fa(c.count)}`).join('، ') : 'هنوز درخواستی ثبت نشده'}</p>
      </Card>
    </div>
  </>}</Async>;
}

const POLICY_FA: Record<string, string> = {cancellation: 'کنسلی', penalty_amount: 'جریمه', penalty_percent: 'درصد جریمه', refundable: 'قابل استرداد', free_cancellation_until: 'کنسلی رایگان تا',
  deadline: 'مهلت', tiers: 'پلکان جریمه', non_refundable: 'غیرقابل استرداد', notes: 'توضیح', description: 'توضیح'};
const HIDDEN_POLICY = new Set(['source', 'verified', 'verified_at', 'version']);
function policyValue(v: unknown): string {
  if (typeof v === 'boolean') return v ? 'بله' : 'خیر';
  if (typeof v === 'number') return fa(v);
  if (v && typeof v === 'object') return Object.entries(v as Record<string, unknown>).filter(([k]) => !HIDDEN_POLICY.has(k)).map(([k, x]) => `${POLICY_FA[k] ?? k}: ${policyValue(x)}`).join('، ');
  return String(v ?? '—');
}
const policyRows = (p: Record<string, unknown>): [string, string][] => Object.entries(p).filter(([k]) => !HIDDEN_POLICY.has(k)).map(([k, v]) => [POLICY_FA[k] ?? k, policyValue(v)]);

const MO_BADGE: Record<string, string> = {not_ready: 'bad', ready: 'warn', waiting_for_provider: 'warn', sent: 'ok', accepted: 'ok', rejected: 'bad'};

function ContractDetail({id, close}: {id: string; close: () => void}) {
  const {state, reload, api} = useLoad<Row>(`/ops/contracts/${id}`);
  const [msg, setMsg] = useState<Msg>(null);
  async function prepare() {setMsg(null); try {await api.post(`/ops/contracts/${id}/moadian`, {}); setMsg({ok: true, text: 'فاکتور برای سامانه‌ی مؤدیان آماده و در صف ارسال قرار گرفت.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Async state={state}>{f => <>
    <Card title={`قرارداد ${f.booking_reference ?? ''}`} action={<button className="pn-btn ghost" onClick={close}>بازگشت</button>}>
      <Stats items={[{label: 'وضعیت', value: f.status_fa}, {label: 'خدمت', value: serviceFa(f.service_type)}, {label: 'مشتری', value: f.customer?.name ?? '—', hint: f.customer?.mobile ?? undefined},
        {label: 'ثبت', value: dateFa(f.created_at), hint: f.confirmed_at ? `تأیید ${dateFa(f.confirmed_at)}` : undefined}]}/>
      {f.sales_case && <p className="pn-muted">از میز فروش: پرونده‌ی {f.sales_case.code} (کانال {CHANNEL_FA[f.sales_case.channel] ?? f.sales_case.channel}{f.sales_case.agent ? `، کارشناس ${f.sales_case.agent}` : ''})</p>}
    </Card>
    <div className="ops-grid">
      <Card title="مسیر پرونده"><ol className="ops-path">{f.path.length ? f.path.map((p: Row, i: number) => <li key={i}><b>{p.title}</b><span className="pn-muted">{dateFa(p.at)} {timeFa(p.at)}{p.actor ? ` — ${p.actor}` : ''}{p.reason ? ` — ${p.reason}` : ''}</span></li>) : <li className="pn-muted">رویدادی ثبت نشده است.</li>}</ol></Card>
      <Card title="خدمات و مالی قرارداد">
        <Stats items={[{label: 'خالص خرید', value: money(f.services.net, f.services.currency)}, {label: 'سود فروش', value: money(f.services.markup, f.services.currency), hint: f.services.markup_reversed ? 'برگشت خورده' : f.services.rule ?? undefined},
          {label: 'مالیات', value: money(f.services.tax, f.services.currency)}, {label: 'مبلغ فروش', value: money(f.services.sell, f.services.currency)},
          {label: 'پرداخت‌شده (درگاه)', value: money(f.finance.paid_gateway, f.finance.currency)}, {label: 'مانده', value: money(f.finance.balance, f.finance.currency)}]}/>
        {f.services.items.length > 0 && <Table rows={f.services.items} rowKey={(r: Row) => r.id} empty="—" cols={[{label: 'قلم', cell: (r: Row) => r.title}, {label: 'تعداد', cell: (r: Row) => r.units ? fa(r.units) : '—'}, {label: 'مبلغ', cell: (r: Row) => money(r.amount, f.services.currency)}]}/>}
        <p className="pn-muted">{f.finance.invoice ? `فاکتور ${f.finance.invoice.number} — ${money(f.finance.invoice.total, f.finance.currency)} (${dateFa(f.finance.invoice.issued_at)})` : 'فاکتور رسمی صادر نشده است.'}</p>
      </Card>
    </div>
    <Card title="پرداخت‌ها و اسناد صندوق"><Table rows={f.payments} rowKey={(r: Row) => r.id} empty="پرداختی ثبت نشده است." cols={[
      {label: 'نوع', cell: (r: Row) => r.kind === 'gateway' ? 'درگاه' : `صندوق (${r.operation})`}, {label: 'مبلغ', cell: (r: Row) => r.kind === 'gateway' ? money(r.captured || r.amount, 'IRR') : money(r.credit || r.debit, 'IRR')},
      {label: 'وضعیت', cell: (r: Row) => r.kind === 'gateway' ? <span className="pn-badge">{r.status}</span> : (r.credit ? 'بستانکار' : 'بدهکار')}, {label: 'پیگیری', cell: (r: Row) => <span className="pn-ltr">{r.reference ?? '—'}</span>}, {label: 'تاریخ', cell: (r: Row) => dateFa(r.at)}]}/></Card>
    <div className="ops-grid">
      <Card title="مسافران">{f.travellers_note && <p className="pn-note">{f.travellers_note}</p>}<Table rows={f.travellers} rowKey={(r: Row) => r.id} empty="مسافری ثبت نشده است." cols={[{label: 'نام', cell: (r: Row) => r.full_name}, {label: 'مدرک', cell: (r: Row) => <span className="pn-ltr">{r.document ?? '—'}</span>}]}/></Card>
      <Card title="کنسلی و درخواست‌ها">
        {policyRows(f.cancellation.policy_at_booking).length ? <dl className="ops-dl">{policyRows(f.cancellation.policy_at_booking).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl> : <p className="pn-muted">قانون کنسلی در لحظه‌ی رزرو ثبت نشده است.</p>}
        <Table rows={f.cancellation.requests} rowKey={(r: Row) => r.id} empty="درخواست کنسلی یا تغییری ثبت نشده است." cols={[{label: 'نوع', cell: (r: Row) => r.type}, {label: 'وضعیت', cell: (r: Row) => <span className="pn-badge">{r.status}</span>}, {label: 'تاریخ', cell: (r: Row) => dateFa(r.at)}]}/>
      </Card>
    </div>
    <Card title="سامانه‌ی مؤدیان" action={<span className={`pn-badge ${MO_BADGE[f.moadian.status]}`}>{f.moadian.status_fa}</span>}>
      <ul className="ops-checks">{f.moadian.checks.map((c: Row) => <li key={c.key}>{c.ok ? '✅' : '❌'} {c.label}</li>)}</ul>
      {f.moadian.status === 'waiting_for_provider' && <p className="pn-note">فاکتور آماده و در صف است. ارسال واقعی بعد از تنظیم کلید امضا و اتصال رسمی سامانه انجام می‌شود؛ تا آن موقع «ارسال شد» نمایش داده نمی‌شود.</p>}
      {f.moadian.error && <p className="pn-note error">{f.moadian.error}</p>}
      <Note msg={msg}/>
      {['ready', 'waiting_for_provider', 'rejected'].includes(f.moadian.status) && <div><button className="pn-btn" onClick={prepare}>{f.moadian.record_id ? 'آماده‌سازی دوباره' : 'آماده‌سازی برای ارسال'}</button></div>}
    </Card>
    {f.support.length > 0 && <Card title="پشتیبانی"><Table rows={f.support} rowKey={(r: Row) => r.id} empty="—" cols={[{label: 'موضوع', cell: (r: Row) => r.subject}, {label: 'وضعیت', cell: (r: Row) => <span className="pn-badge">{r.status}</span>}]}/></Card>}
  </>}</Async>;
}

function MoadianSettings() {
  const {state, reload, api} = useLoad<Row>('/ops/moadian/settings');
  const [form, setForm] = useState<Row | null>(null); const [msg, setMsg] = useState<Msg>(null);
  return <Async state={state}>{s => {
    const v = form ?? {economic_code: s.economic_code ?? '', memory_id: s.memory_id ?? '', codes: Object.entries(s.service_codes).map(([k, c]) => `${k}=${c}`).join('\n')};
    async function save(e: FormEvent) {
      e.preventDefault(); setMsg(null);
      const codes: Record<string, string> = {};
      for (const line of String(v.codes).split('\n').map(x => x.trim()).filter(Boolean)) {const [k, c] = line.split('='); codes[(k ?? '').trim()] = (c ?? '').trim();}
      try {await api.put('/ops/moadian/settings', {economic_code: v.economic_code || null, memory_id: v.memory_id || null, service_codes: codes}); setForm(null); setMsg({ok: true, text: 'تنظیمات مؤدیان ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}
    }
    return <Card title="تنظیمات سامانه‌ی مؤدیان">
      <p className="pn-note">{s.provider_note}</p><Note msg={msg}/>
      <form className="pn-form" onSubmit={save}>
        <label>شناسه‌ی ملی / کد اقتصادی فروشنده<input className="pn-ltr" value={v.economic_code} onChange={e => setForm({...v, economic_code: e.target.value})} inputMode="numeric"/></label>
        <label>شناسه‌ی یکتای حافظه‌ی مالیاتی<input className="pn-ltr" value={v.memory_id} maxLength={6} onChange={e => setForm({...v, memory_id: e.target.value})}/></label>
        <label>شناسه‌ی خدمت (هر خط: نوع=۱۳ رقم، مثل hotel=2720000114542)<textarea className="pn-ltr" rows={4} value={v.codes} onChange={e => setForm({...v, codes: e.target.value})}/></label>
        <button className="pn-btn">ثبت (مدیر مجموعه)</button>
      </form>
    </Card>;
  }}</Async>;
}

export function ContractFiles({initialId}: {initialId?: string | null}) {
  const [q, setQ] = useState(''); const [query, setQuery] = useState('');
  const [open, setOpen] = useState<string | null>(initialId ?? null);
  const [settings, setSettings] = useState(false);
  const {state} = useLoad<Row>(`/ops/contracts${query ? `?q=${encodeURIComponent(query)}` : ''}`);
  if (open) return <ContractDetail id={open} close={() => setOpen(null)}/>;
  if (settings) return <><button className="pn-btn ghost" onClick={() => setSettings(false)}>بازگشت به قراردادها</button><MoadianSettings/></>;
  return <Card title="جستجوی قرارداد" action={<button className="pn-btn ghost" onClick={() => setSettings(true)}>تنظیمات مؤدیان</button>}>
    <form className="ops-row" onSubmit={e => {e.preventDefault(); setQuery(q.trim());}}>
      <input aria-label="شماره قرارداد، نام یا موبایل مشتری" placeholder="شماره قرارداد، نام یا موبایل مشتری" value={q} onChange={e => setQ(e.target.value)}/><button className="pn-btn">جستجو</button></form>
    <Async state={state}>{d => <Table rows={d.items} rowKey={(r: Row) => r.id} empty="قراردادی پیدا نشد." cols={[
      {label: 'شماره', cell: (r: Row) => <span className="pn-ltr">{r.booking_reference ?? r.id.slice(0, 8)}</span>}, {label: 'خدمت', cell: (r: Row) => serviceFa(r.service_type)},
      {label: 'مشتری', cell: (r: Row) => r.customer}, {label: 'مبلغ', cell: (r: Row) => money(r.amount, 'IRR')}, {label: 'وضعیت', cell: (r: Row) => <span className="pn-badge">{r.status_fa}</span>},
      {label: 'ثبت', cell: (r: Row) => dateFa(r.created_at)}, {label: '', cell: (r: Row) => <button className="pn-btn ghost" onClick={() => setOpen(r.id)}>پرونده</button>}]}/>}</Async>
  </Card>;
}
