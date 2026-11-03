'use client';
/* General ledger: periods (post treasury, close/reopen), vouchers (manual, reverse), trial balance, chart & posting rules. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Stats, Table, errorOf, fa, money, useLoad} from './PanelKit';
import {Note, Tabs, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;
const SOURCE_FA: Record<string, string> = {manual: 'دستی', treasury: 'صندوق', reversal: 'برگشتی'};
const OP_FA: Record<string, string> = {deposit: 'واریز', withdrawal: 'برداشت', purchase: 'خرید', refund: 'استرداد', settlement: 'تسویه', adjustment: 'اصلاح', fee: 'کارمزد', revenue: 'درآمد'};
const ACC_TYPES: [string, string][] = [['wallet', 'کیف پول'], ['credit', 'اعتبار'], ['receivable', 'دریافتنی'], ['payable', 'پرداختنی'], ['bank', 'بانک'], ['cash', 'نقد'], ['gateway', 'درگاه'], ['revenue', 'درآمد']];
const periodFa = (p: string) => p.replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]).replace('-', '/');

function Periods() {
  const {state, reload, api} = useLoad<Row>('/ledger/periods');
  const [msg, setMsg] = useState<Msg>(null); const [plan, setPlan] = useState<Row | null>(null);
  async function run(fn: () => Promise<void>) {setMsg(null); try {await fn(); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  const preview = (period: string) => run(async () => setPlan(await api.post<Row>('/ledger/post-treasury', {period})));
  const post = (period: string) => run(async () => {const r = await api.post<Row>('/ledger/post-treasury', {period, confirm: true}); setPlan(null); setMsg({ok: true, text: `${fa(r.created)} سند از ردیف‌های صندوق ساخته شد.`});});
  const close = (period: string) => run(async () => {await api.post(`/ledger/periods/${period}/close`, {}); setMsg({ok: true, text: `دوره‌ی ${periodFa(period)} بسته شد.`});});
  const reopen = (period: string) => {const reason = window.prompt('دلیل باز کردن دوره‌ی بسته'); if (reason) void run(async () => {await api.post(`/ledger/periods/${period}/reopen`, {reason}); setMsg({ok: true, text: 'دوره باز شد.'});});};
  return <Async state={state}>{d => <Card title="دوره‌های مالی (ماه شمسی)">
    <Note msg={msg}/>
    {plan && <div className="pn-note"><b>پیش‌نمایش {periodFa(plan.period)}:</b> {fa(plan.ready)} ردیف آماده‌ی سند ({money(plan.amount, 'IRR')}){plan.missing.length ? ` — بدون کد: ${plan.missing.map((x: Row) => `${x.reason} (${fa(x.count)})`).join('، ')}` : ''}
      {plan.ready > 0 && <> <button className="pn-btn" onClick={() => void post(plan.period)}>ساخت {fa(plan.ready)} سند</button></>}</div>}
    <Table rows={d.items} rowKey={(r: Row) => r.period} empty="هنوز ردیف یا سندی ثبت نشده است." cols={[
      {label: 'دوره', cell: (r: Row) => <b>{periodFa(r.period)}</b>}, {label: 'سند', cell: (r: Row) => fa(r.vouchers)}, {label: 'ردیف صندوق', cell: (r: Row) => fa(r.treasury_entries)},
      {label: 'بدون سند', cell: (r: Row) => r.unposted ? <span className="pn-badge warn">{fa(r.unposted)}</span> : <span className="pn-badge ok">۰</span>},
      {label: 'وضعیت', cell: (r: Row) => r.status === 'closed' ? <span className="pn-badge ok">بسته</span> : <span className="pn-badge">باز</span>},
      {label: '', cell: (r: Row) => <span className="sec-actions">
        {r.status !== 'closed' && r.unposted > 0 && <button className="pn-btn ghost" onClick={() => void preview(r.period)}>سند صندوق</button>}
        {r.status !== 'closed' && <button className="pn-btn ghost" onClick={() => void close(r.period)}>بستن</button>}
        {r.status === 'closed' && <button className="pn-btn ghost" onClick={() => reopen(r.period)}>باز کردن</button>}</span>}]}/>
  </Card>}</Async>;
}

function TrialBalance() {
  const periods = useLoad<Row>('/ledger/periods');
  const [picked, setPicked] = useState<string | null>(null);
  const list: Row[] = periods.state.kind === 'ready' ? periods.state.data.items : [];
  const period = picked ?? list[0]?.period ?? null;
  const {state, api} = useLoad<Row>(period ? `/ledger/trial-balance?period=${period}` : null);
  const chooser = <select aria-label="دوره" value={period ?? ''} onChange={e => setPicked(e.target.value)}>{list.map(p => <option key={p.period} value={p.period}>{periodFa(p.period)}</option>)}</select>;
  const [msg, setMsg] = useState<Msg>(null);
  async function download(fmt: string) {
    setMsg(null);
    try {const b = await api.getBlob(`/ledger/export?period=${period}&fmt=${fmt}`); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `karenseir-vouchers-${period}.${fmt}`; a.click(); URL.revokeObjectURL(a.href);}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  if (!period) return <Async state={periods.state}>{() => <p className="pn-muted">هنوز دوره‌ای برای تراز نیست.</p>}</Async>;
  return <Async state={state}>{t => <Card title={`تراز آزمایشی ${periodFa(t.period)}`} action={<span className="sec-actions">{chooser}<button className="pn-btn ghost" onClick={() => void download('xlsx')}>خروجی اسناد (اکسل فرانگر)</button><button className="pn-btn ghost" onClick={() => void download('csv')}>CSV</button></span>}>
    <Note msg={msg}/>
    <Stats items={[{label: 'جمع بدهکار', value: money(t.totals.debit, 'IRR')}, {label: 'جمع بستانکار', value: money(t.totals.credit, 'IRR')}, {label: 'وضعیت', value: t.balanced ? 'تراز است' : 'تراز نیست'}, {label: 'دوره', value: t.closed ? 'بسته' : 'باز'}]}/>
    <Table rows={t.items} rowKey={(r: Row) => r.code} empty="در این دوره سندی ثبت نشده است." cols={[
      {label: 'کد', cell: (r: Row) => <span className="pn-ltr">{r.code}</span>}, {label: 'حساب', cell: (r: Row) => r.title ?? '—'}, {label: 'مانده‌ی اول دوره', cell: (r: Row) => money(r.opening, 'IRR')},
      {label: 'بدهکار', cell: (r: Row) => money(r.debit, 'IRR')}, {label: 'بستانکار', cell: (r: Row) => money(r.credit, 'IRR')}, {label: 'مانده‌ی پایان دوره', cell: (r: Row) => money(r.closing, 'IRR')}]}/>
  </Card>}</Async>;
}

function Vouchers() {
  const {state, reload, api} = useLoad<Row>('/ledger/vouchers');
  const accounts = useLoad<Row>('/ledger/accounts');
  const [open, setOpen] = useState<Row | null>(null); const [msg, setMsg] = useState<Msg>(null);
  const [form, setForm] = useState<Row>({voucher_date: new Date().toISOString().slice(0, 10), description: '', lines: [{account_code: '', debit: '', credit: ''}, {account_code: '', debit: '', credit: ''}]});
  const lines: Row[] = form.lines; const td = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0), tc = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0);
  const setLine = (i: number, k: string, v: string) => setForm({...form, lines: lines.map((l, j) => j === i ? {...l, [k]: k === 'account_code' ? v : v.replace(/[^\d]/g, '')} : l)});
  async function save(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    try {const v = await api.post<Row>('/ledger/vouchers', {...form, lines: lines.filter(l => l.account_code).map(l => ({account_code: l.account_code, debit: Number(l.debit) || 0, credit: Number(l.credit) || 0}))});
      setMsg({ok: true, text: `سند ${fa(v.number)} ثبت شد.`}); setForm({...form, description: '', lines: [{account_code: '', debit: '', credit: ''}, {account_code: '', debit: '', credit: ''}]}); reload();}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  async function view(id: string) {setMsg(null); try {setOpen(await api.get<Row>(`/ledger/vouchers/${id}`));} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  async function reverse(id: string) {const reason = window.prompt('دلیل برگشت سند'); if (!reason) return; setMsg(null); try {await api.post(`/ledger/vouchers/${id}/reverse`, {reason}); setOpen(null); setMsg({ok: true, text: 'سند برگشتی ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  const options = accounts.state.kind === 'ready' ? (accounts.state.data.items as Row[]).filter(a => a.active) : [];
  return <>
    <Note msg={msg}/>
    {open && <Card title={`سند ${fa(open.number)} — ${open.description}`} action={<span className="sec-actions">{open.status === 'posted' && open.source !== 'reversal' && <button className="pn-btn ghost" onClick={() => void reverse(open.id)}>برگشت سند</button>}<button className="pn-btn ghost" onClick={() => setOpen(null)}>بستن</button></span>}>
      <Table rows={open.lines} rowKey={(r: Row) => String(r.line_no)} empty="—" cols={[{label: 'ردیف', cell: (r: Row) => fa(r.line_no)}, {label: 'حساب', cell: (r: Row) => `${r.account_code} ${r.account_title ?? ''}`},
        {label: 'طرف حساب', cell: (r: Row) => r.counterparty ?? '—'}, {label: 'بدهکار', cell: (r: Row) => r.debit ? money(r.debit, 'IRR') : ''}, {label: 'بستانکار', cell: (r: Row) => r.credit ? money(r.credit, 'IRR') : ''}]}/></Card>}
    <Card title="سند دستی">
      <form className="pn-form" onSubmit={save}>
        <label>تاریخ<input type="date" dir="ltr" value={form.voucher_date} onChange={e => setForm({...form, voucher_date: e.target.value})} required/></label>
        <label>شرح<input value={form.description} onChange={e => setForm({...form, description: e.target.value})} required minLength={3}/></label>
        {lines.map((l, i) => <div key={i} className="gl-line">
          <select aria-label={`حساب ردیف ${i + 1}`} value={l.account_code} onChange={e => setLine(i, 'account_code', e.target.value)}><option value="">حساب…</option>{options.map(a => <option key={a.code} value={a.code}>{a.code} — {a.title}</option>)}</select>
          <input aria-label={`بدهکار ردیف ${i + 1}`} placeholder="بدهکار" inputMode="numeric" value={l.debit} onChange={e => setLine(i, 'debit', e.target.value)}/>
          <input aria-label={`بستانکار ردیف ${i + 1}`} placeholder="بستانکار" inputMode="numeric" value={l.credit} onChange={e => setLine(i, 'credit', e.target.value)}/></div>)}
        <div className="sec-actions"><button type="button" className="pn-btn ghost" onClick={() => setForm({...form, lines: [...lines, {account_code: '', debit: '', credit: ''}]})}>ردیف تازه</button>
          <span className={`pn-badge ${td === tc && td > 0 ? 'ok' : 'warn'}`}>بدهکار {fa(td)} / بستانکار {fa(tc)}</span><button className="pn-btn" disabled={td !== tc || td === 0}>ثبت سند</button></div>
      </form>
    </Card>
    <Async state={state}>{d => <Card title="اسناد"><Table rows={d.items} rowKey={(r: Row) => r.id} empty="سندی ثبت نشده است." cols={[
      {label: 'شماره', cell: (r: Row) => fa(r.number)}, {label: 'تاریخ', cell: (r: Row) => <span className="pn-ltr">{r.voucher_date}</span>}, {label: 'دوره', cell: (r: Row) => periodFa(r.period)},
      {label: 'شرح', cell: (r: Row) => r.description}, {label: 'منبع', cell: (r: Row) => SOURCE_FA[r.source] ?? r.source}, {label: 'مبلغ', cell: (r: Row) => money(r.total, 'IRR')},
      {label: 'وضعیت', cell: (r: Row) => r.status === 'reversed' ? <span className="pn-badge bad">برگشت خورده</span> : <span className="pn-badge ok">ثبت شده</span>},
      {label: '', cell: (r: Row) => <button className="pn-btn ghost" onClick={() => void view(r.id)}>ردیف‌ها</button>}]}/></Card>}</Async>
  </>;
}

function ChartAndRules() {
  const acc = useLoad<Row>('/ledger/accounts'); const rules = useLoad<Row>('/ledger/posting-rules');
  const [chartText, setChartText] = useState<string | null>(null); const [rulesText, setRulesText] = useState<string | null>(null); const [msg, setMsg] = useState<Msg>(null);
  const KIND_KEYS: Record<string, string> = {'دارایی': 'asset', 'بدهی': 'liability', 'سرمایه': 'equity', 'درآمد': 'revenue', 'هزینه': 'expense'};
  async function saveChart(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    const items = String(chartText ?? '').split('\n').map(l => l.trim()).filter(Boolean).map(l => {const [code, title, kind, off] = l.split('|').map(x => x.trim()); return {code, title, kind: KIND_KEYS[kind] ?? kind, active: off !== 'غیرفعال'};});
    try {await acc.api.put('/ledger/accounts', {items}); setChartText(null); setMsg({ok: true, text: 'سرفصل‌ها ثبت شد.'}); acc.reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  async function saveRules(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    const items = String(rulesText ?? '').split('\n').map(l => l.trim()).filter(Boolean).map(l => {const [operation, account_type, counter_code] = l.split('|').map(x => x.trim()); return {operation, account_type, counter_code};});
    try {await rules.api.put('/ledger/posting-rules', {items}); setRulesText(null); setMsg({ok: true, text: 'قواعد طرف مقابل ثبت شد.'}); rules.reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  return <>
    <Note msg={msg}/>
    <div className="ops-grid">
      <Async state={acc.state}>{a => <Card title="سرفصل حساب‌ها">
        <p className="pn-muted">هر خط: کد | عنوان | نوع (دارایی، بدهی، سرمایه، درآمد، هزینه) | «غیرفعال» در صورت نیاز. کدها همان کدهای فرانگر شما باشند.</p>
        <form className="pn-form" onSubmit={saveChart}><textarea rows={10} dir="rtl" aria-label="سرفصل حساب‌ها" value={chartText ?? (a.items as Row[]).map(x => `${x.code} | ${x.title} | ${x.kind_fa}${x.active ? '' : ' | غیرفعال'}`).join('\n')} onChange={e => setChartText(e.target.value)}/>
          <button className="pn-btn">ثبت سرفصل‌ها</button></form></Card>}</Async>
      <Async state={rules.state}>{r => <Card title="قواعد طرف مقابل صندوق">
        <p className="pn-muted">هر ردیف صندوق یک‌طرفه است؛ طرف دیگر سند از این قواعد می‌آید. هر خط: عملیات | نوع حساب | کد حساب طرف مقابل.</p>
        <p className="pn-muted">عملیات: {Object.entries(OP_FA).map(([k, v]) => `${k} (${v})`).join('، ')} — نوع حساب: {ACC_TYPES.map(([k, v]) => `${k} (${v})`).join('، ')}</p>
        <form className="pn-form" onSubmit={saveRules}><textarea rows={8} dir="ltr" aria-label="قواعد طرف مقابل" value={rulesText ?? (r.items as Row[]).map(x => `${x.operation} | ${x.account_type} | ${x.counter_code}`).join('\n')} onChange={e => setRulesText(e.target.value)}/>
          <button className="pn-btn">ثبت قواعد</button></form></Card>}</Async>
    </div>
  </>;
}

export function Ledger() {
  return <Tabs tabs={[['دوره‌ها و بستن', <Periods key="p"/>], ['تراز آزمایشی', <TrialBalance key="t"/>], ['اسناد', <Vouchers key="v"/>], ['سرفصل‌ها و قواعد', <ChartAndRules key="c"/>]]}/>;
}
