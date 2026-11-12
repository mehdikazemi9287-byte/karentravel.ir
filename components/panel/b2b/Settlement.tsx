'use client';
/* Panels Phase 2b (Figma "Panels / P3 Settlement+Charter ops" 243:2): AG-17 agency settlements list/detail, AG-18a dispute open,
   FIN-05 finance settlements list/detail, FIN-08 dispute resolve, FIN-02c refund to agency credit, OPS-CH-05/05b charter
   schedule change/cancel with impact preview, AG-CH-06 agency notice. Every amount comes from the API (integer rial, server-side
   math); money actions are maker-checker requests a second person approves. Nothing here computes a commission or a tax. */
import Link from 'next/link';
import {useParams, useRouter} from 'next/navigation';
import {useState, type ReactNode} from 'react';
import {AgencyScope} from '../AgencyPanel';
import {Card, Stats, Table, useLoad} from '../PanelKit';
import {ConfirmMoney, DecisionDialog, EmptyState, Loaded, Ref, Skeleton, Timeline, Unavail, amountWords, newKey, rial} from '../aftersales/kit';
import {DateField, Feedback, Field, StatusChip, jalali, parseRial, pct, tehranIso, useAction} from './B2BKit';

type Agency = {id: string; name: string};
type Totals = {opening_owed_irr: number; sales_irr: number; refunds_irr: number; payments_irr: number; previous_settlement_irr: number; commission_irr: number; vat_irr: number; adjustments_irr: number; net_irr: number};
type Line = {id: string; line_no: number; line_type: string; type_label: string; amount_irr: number; description: string; reservation_id: string | null; vat_rate_bps: number | null; occurred_at: string | null; open_dispute_id: string | null; disputable: boolean};
type BookingRow = {key: string; reservation_id: string; booking_reference: string | null; kind: 'sale' | 'refund'; date: string | null; sale_irr: number; refund_irr: number; commission_irr: number; vat_irr: number; net_irr: number; line_id: string | null; open_dispute_id: string | null; disputable: boolean};
type Dispute = {id: string; settlement_id: string; line_id: string; line_no: number | null; line_type: string | null; line_amount_irr: number | null; line_description: string | null; reason: string; claimed_amount_irr: number; status: string; status_label: string; adjustment_amount_irr: number | null; resolution_note: string | null; mc_request_id: string | null; opened_by: string | null; resolved_by: string | null; created_at: string; resolved_at: string | null; statement_no?: string; agency_name?: string; age_hours?: number};
type Statement = {id: string; statement_no: string; agency_id: string; agency_name: string | null; period_start: string; period_end: string; status: string; status_label: string; net_irr: number; totals: Totals; direction: 'agency_pays' | 'platform_owes' | 'zero'; issued_at: string | null; accepted_at: string | null; settled_at: string | null; settle_reference: string | null; created_at: string;
  issue_request?: {id: string; status: string} | null; settle_request?: {id: string; status: string} | null;
  lines?: Line[]; booking_rows?: BookingRow[]; disputes?: Dispute[]; timeline?: {type: string; actor: string | null; note: string | null; at: string | null; dispute_id: string | null}[]; can_act?: boolean; can_manage?: boolean};
type CreditRefund = {id: string; agency_id: string; agency_name?: string; booking_reference: string | null; source: string; amount_irr: number; penalty_irr: number; status: string; status_label: string; mc_request_id: string | null; executed_at: string | null; created_at: string};
type McReq = {id: string; kind: string; status: string; payload: Record<string, unknown>; mine: boolean; can_decide: boolean; maker_user_id: number};

/* Settlement status → StatusChip tone (FIGMA_MAP_P3 «Settlement status»). */
const ST_TONE: Record<string, [string, string, string]> = {draft: ['closed', 'پیش‌نویس', 'پیش‌نویس'], issued: ['under_review', 'منتظر تأیید آژانس', 'منتظر تأیید شما'], accepted: ['submitted', 'منتظر پرداخت', 'تأییدشده · منتظر پرداخت'],
  disputed: ['rejected', 'مورد اعتراض', 'مورد اعتراض'], settled: ['approved', 'تسویه‌شده', 'تسویه‌شده'], superseded: ['closed', 'جایگزین‌شده', 'جایگزین‌شده']};
export function SettlementChip({status, agency}: {status: string; agency?: boolean}) {const t = ST_TONE[status]; return <StatusChip status={t?.[0] ?? status} label={t ? t[agency ? 2 : 1] : status}/>;}
const signed = (n: number) => (n < 0 ? `− ${rial(-n)}` : rial(n));
const dirFa = (d: Statement['direction'], agency = false) => d === 'agency_pays' ? (agency ? 'بدهی شما' : 'دریافتنی از آژانس') : d === 'platform_owes' ? (agency ? 'طلب شما' : 'پرداختنی به آژانس') : 'صفر';

/** Status stepper (desktop pills; mobile one-line note). */
function Stepper({status, agency}: {status: string; agency?: boolean}) {
  const steps = status === 'disputed' ? ['draft', 'issued', 'disputed', 'resolve', 'accepted', 'settled'] : ['draft', 'issued', 'accepted', 'settled'];
  const label: Record<string, string> = {draft: 'پیش‌نویس', issued: 'صادرشده', disputed: 'مورد اعتراض', resolve: 'حل اختلاف', accepted: agency ? 'تأیید شما یا اعتراض' : 'تأیید آژانس', settled: 'تسویه‌شده'};
  const cur = status === 'disputed' ? 3 : status === 'issued' ? 2 : status === 'accepted' ? 3 : status === 'settled' ? 4 : 0;
  return <><ol className="b2b-steps" aria-label="مراحل صورت تسویه">{steps.map((s, i) => <li key={s} data-state={s === 'disputed' ? 'bad' : i < cur || status === 'settled' ? 'done' : i === cur ? 'current' : 'next'} aria-current={i === cur ? 'step' : undefined}>{i > 0 && <span className="b2b-step-arrow" aria-hidden="true">←</span>}<span className="b2b-step">{i < cur || status === 'settled' ? '✓ ' : ''}{label[s]}</span></li>)}</ol>
    <p className="b2b-steps-mobile as-muted">گام {Math.min(cur + 1, steps.length).toLocaleString('fa-IR')} از {steps.length.toLocaleString('fa-IR')} · {label[steps[Math.min(cur, steps.length - 1)]]}</p></>;
}

function Summary({s, agency}: {s: Statement; agency?: boolean}) {
  const t = s.totals; const other = t.opening_owed_irr + t.payments_irr + t.previous_settlement_irr;
  return <Card title="خلاصهٔ مبالغ دوره" action={<span className="as-muted">واحد: ریال · محاسبهٔ سمت سرور</span>}>
    <dl className="b2b-sum">
      <div><dt>فروش با حساب آژانس</dt><dd>{rial(t.sales_irr)}</dd></div>
      <div><dt>استردادهای برگشت‌داده‌شده به اعتبار</dt><dd>{signed(t.refunds_irr)}</dd></div>
      <div className="soft"><dt>فروش خالص دوره</dt><dd>{rial(t.sales_irr + t.refunds_irr)}</dd></div>
      <div><dt>کمیسیون آژانس (پس از برگشت‌ها)</dt><dd>{signed(t.commission_irr)}</dd></div>
      <div><dt>ارزش افزوده — فقط روی کمیسیون</dt><dd>{signed(t.vat_irr)}</dd></div>
      <div><dt>مانده و پرداخت‌های حساب (ابتدای دوره، واریزها، تسویهٔ قبلی)</dt><dd>{signed(other)}</dd></div>
      <div><dt>تعدیل‌های اختلاف و اصلاحیه‌ها</dt><dd>{signed(t.adjustments_irr)}</dd></div>
      <div className="total"><dt>{s.direction === 'platform_owes' ? (agency ? 'طلب خالص شما از کارن تراول' : 'خالص پرداختنی به آژانس') : (agency ? 'بدهی خالص شما به کارن تراول' : 'خالص دریافتنی از آژانس')}</dt><dd>{rial(Math.abs(s.net_irr))}</dd></div>
    </dl>
    <p className="as-muted">ارزش افزوده روی فروش محاسبه نمی‌شود، فقط روی کمیسیون و با نرخ تاریخ فروش از جدول تاریخ‌دار. استرداد، کمیسیون و ارزش افزودهٔ همان رزرو را به نسبت برمی‌گرداند. طلب منفی پس از تسویه به‌صورت اعتبار در حساب آژانس می‌ماند.</p>
  </Card>;
}

function StatementTimeline({s}: {s: Statement}) {
  const T: Record<string, string> = {drafted: 'ساخت پیش‌نویس', issue_requested: 'درخواست صدور (نفر اول مالی)', issued: 'صدور صورت (تأیید نفر دوم مالی)', accepted: 'تأیید صورت توسط آژانس', dispute_opened: 'ثبت اعتراض آژانس',
    dispute_adjustment_requested: 'پذیرش با اصلاحیه — منتظر نفر دوم', dispute_accepted: 'پذیرش اعتراض', dispute_rejected: 'رد اعتراض', disputes_closed: 'بسته شدن اعتراض‌ها', adjustment_requested: 'درخواست اصلاحیه',
    adjustment_added: 'افزودن ردیف اصلاحیه', settle_requested: 'درخواست ثبت تسویه', settled: 'تسویه‌شده', superseded: 'جایگزین با پیش‌نویس تازه'};
  const next = s.status === 'issued' ? {title: 'تأیید یا اعتراض آژانس', owner: 'آژانس', eta: null, overdue: false} : s.status === 'disputed' ? {title: 'رسیدگی مالی به اعتراض', owner: 'مالی', eta: null, overdue: false}
    : s.status === 'accepted' ? {title: 'ثبت پرداخت با کد پیگیری بانکی (دو نفر مالی)', owner: 'مالی', eta: null, overdue: false} : s.status === 'draft' ? {title: 'صدور با تأیید نفر دوم مالی', owner: 'مالی', eta: null, overdue: false} : null;
  return <Card title="وضعیت دوطرفه"><Timeline steps={(s.timeline ?? []).map((e, i) => ({id: `${i}`, title: T[e.type] ?? e.type, actor: e.actor, at: e.at, note: e.note, type: e.type === 'dispute_rejected' ? 'reject' : e.type}))} next={next}/></Card>;
}

function useMine(agencyId: string | undefined, match: (r: McReq) => boolean) {
  const q = useLoad<{items: McReq[]}>(agencyId ? '/maker-checker/requests?status=pending' : null);
  return {reqs: q.state.kind === 'ready' ? q.state.data.items.filter(match) : [], reload: q.reload};
}
function Approve({req, onDone, label = 'تأیید (نفر دوم)'}: {req: McReq; onDone: (message: string) => void; label?: string}) {
  const act = useAction();
  if (req.mine) return <span className="as-chip warn">ثبت شما؛ نفر دوم تأیید می‌کند</span>;
  if (!req.can_decide) return <span className="as-chip warn">منتظر تأیید نفر دوم</span>;
  return <span className="as-row"><button type="button" className="as-btn" disabled={act.busy} onClick={async () => {if (await act.run(api => api.post(`/maker-checker/requests/${req.id}/approve`, {}))) onDone('تأیید و اعمال شد.');}}>{label}</button>
    <button type="button" className="as-btn ghost" disabled={act.busy} onClick={async () => {if (await act.run(api => api.post(`/maker-checker/requests/${req.id}/reject`, {note: 'رد توسط نفر دوم'}))) onDone('درخواست رد شد.');}}>رد</button><Feedback error={act.error} done={act.done}/></span>;
}

/* ================================================================ AG-17 agency list */
export function AgencySettlementsPage() {return <AgencyScope>{a => <AgList a={a}/>}</AgencyScope>;}
function AgList({a}: {a: Agency}) {
  const q = useLoad<{items: Statement[]; credit_refunds: CreditRefund[]; awaiting_action: number}>(`/agency/${a.id}/settlement-statements`); const [f, setF] = useState('');
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton kind="table"/>}>{d => {
    const open = d.items.find(s => s.status !== 'settled'); const rows = d.items.filter(s => !f || s.status === f);
    return <>
      <Stats items={[{label: 'منتظر تأیید شما', value: d.awaiting_action.toLocaleString('fa-IR')}, {label: open ? dirFa(open.direction, true) : 'صورت باز', value: open ? rial(Math.abs(open.net_irr)) : 'ندارد'},
        {label: 'اعتراض‌های باز', value: d.items.filter(s => s.status === 'disputed').length.toLocaleString('fa-IR')}, {label: 'تسویه‌شده', value: d.items.filter(s => s.status === 'settled').length.toLocaleString('fa-IR')}]}/>
      <Card title="صورت‌های تسویهٔ دوره‌ای">
        <div className="pn-chips b2b-pills" role="group" aria-label="وضعیت">{[['', 'همه'], ['issued', 'منتظر تأیید شما'], ['disputed', 'مورد اعتراض'], ['accepted', 'تأییدشده'], ['settled', 'تسویه‌شده']].map(([k, l]) => <button key={k || 'all'} type="button" aria-pressed={f === k} onClick={() => setF(k)}>{l}</button>)}</div>
        {rows.length ? <Table rows={rows} rowKey={s => s.id} empty="" cols={[{label: 'شمارهٔ صورت', cell: s => <Ref>{s.statement_no}</Ref>}, {label: 'دوره', cell: s => `${jalali(s.period_start)} تا ${jalali(s.period_end)}`},
          {label: 'فروش', cell: s => rial(s.totals.sales_irr)}, {label: 'استرداد به اعتبار', cell: s => signed(s.totals.refunds_irr)}, {label: 'کمیسیون + VAT', cell: s => signed(s.totals.commission_irr + s.totals.vat_irr)},
          {label: 'خالص', cell: s => <b>{rial(Math.abs(s.net_irr))} <small className="as-muted">({dirFa(s.direction, true)})</small></b>}, {label: 'وضعیت', cell: s => <SettlementChip status={s.status} agency/>},
          {label: 'اقدام', cell: s => <Link className={`as-btn ${s.status === 'issued' ? '' : 'ghost'}`} href={`/agency/settlements/${s.id}`}>{s.status === 'issued' ? 'بررسی و تأیید' : 'مشاهده'}</Link>}]}/>
          : <EmptyState title="صورتی نیست">هنوز صورت تسویه‌ای برای این آژانس صادر نشده است. پیش‌نویس‌ها فقط برای مالی دیده می‌شوند.</EmptyState>}
        <p className="as-note info">خالص = فروش − استرداد به اعتبار − کمیسیون − ارزش افزودهٔ کمیسیون، با احتساب ماندهٔ حساب و واریزهای دوره. مهلت تأیید و قاعدهٔ تأیید ضمنی هنوز تصمیم مالک است (OQ-O6) و اجرا نمی‌شود.</p>
      </Card>
      <Card title="بازگشت‌های اخیر به اعتبار آژانس">
        <Table rows={d.credit_refunds} rowKey={r => r.id} empty="بازگشتی به اعتبار ثبت نشده است." cols={[{label: 'رزرو', cell: r => <Ref>{r.booking_reference ?? '—'}</Ref>}, {label: 'منشأ', cell: r => SOURCE_FA[r.source] ?? r.source},
          {label: 'مبلغ', cell: r => rial(r.amount_irr)}, {label: 'وضعیت', cell: r => <StatusChip status={r.status === 'executed' ? 'approved' : r.status === 'pending_approval' ? 'under_review' : 'rejected'} label={r.status_label}/>}, {label: 'تاریخ', cell: r => jalali(r.executed_at ?? r.created_at, true)}]}/>
      </Card></>;}}</Loaded></div>;
}
const SOURCE_FA: Record<string, string> = {service_request: 'لغو یا استرداد رزرو', charter_cancel: 'لغو پرواز چارتر', charter_change: 'تغییر زمان پرواز چارتر'};

/* ================================================================ AG-17 detail + AG-18a dispute */
export function AgencySettlementDetailPage() {const p = useParams<{id: string}>(); return <AgencyScope>{a => <AgDetail a={a} id={String(p?.id ?? '')}/>}</AgencyScope>;}
function AgDetail({a, id}: {a: Agency; id: string}) {
  const q = useLoad<Statement>(`/agency/${a.id}/settlement-statements/${id}`); const act = useAction(); const [line, setLine] = useState<{id: string; label: string; amount: number} | null>(null);
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton/>}>{s => <>
    <div className="as-card-head"><div><h2>صورت تسویه <Ref>{s.statement_no}</Ref></h2><p className="as-muted">دوره {jalali(s.period_start)} تا {jalali(s.period_end)}{s.issued_at ? ` · صدور ${jalali(s.issued_at, true)}` : ''}</p></div><SettlementChip status={s.status} agency/></div>
    <Stepper status={s.status} agency/>
    {s.status === 'issued' && <p className="as-note warn">صورت منتظر تأیید یا اعتراض شماست. قاعدهٔ مهلت و تأیید ضمنی هنوز تصمیم مالک است (OQ-O6) و فعلاً اعمال نمی‌شود.</p>}
    <div className="as-grid2"><Summary s={s} agency/><StatementTimeline s={s}/></div>
    <Card title="ردیف‌های صورت تسویه" action={<span className="as-muted">برای اعتراض، روی ردیف «اعتراض» بزنید.</span>}>
      <Table rows={s.booking_rows ?? []} rowKey={r => r.key} empty="در این دوره فروش یا استردادی با حساب آژانس نیست." cols={[{label: 'کد رزرو', cell: r => <Ref>{r.booking_reference ?? '—'}</Ref>}, {label: 'تاریخ', cell: r => jalali(r.date)},
        {label: 'نوع', cell: r => r.kind === 'refund' ? 'استرداد → اعتبار' : 'فروش'}, {label: 'مبلغ فروش', cell: r => rial(r.sale_irr)}, {label: 'استرداد', cell: r => signed(r.refund_irr)},
        {label: 'کمیسیون', cell: r => signed(r.commission_irr)}, {label: 'VAT کمیسیون', cell: r => signed(r.vat_irr)}, {label: 'خالص ردیف', cell: r => signed(r.net_irr)},
        {label: 'اقدام', cell: r => r.open_dispute_id ? <StatusChip status="rejected" label="اعتراض باز"/> : r.disputable && s.can_act ? <button type="button" className="as-btn ghost" onClick={() => setLine({id: r.line_id!, label: `${r.booking_reference ?? ''} · ${r.kind === 'refund' ? 'استرداد' : 'فروش'}`, amount: Math.abs(r.net_irr)})}>اعتراض</button> : '—'}]}/>
      <OtherLines s={s} canAct={!!s.can_act} onDispute={l => setLine({id: l.id, label: l.type_label, amount: Math.abs(l.amount_irr)})}/>
      {s.can_act && <div className="as-actions as-sticky"><button type="button" className="as-btn" disabled={act.busy || s.status !== 'issued'} onClick={async () => {if (await act.run(api => api.post(`/agency/${a.id}/settlement-statements/${s.id}/accept`, {}), 'صورت تسویه تأیید شد.')) q.reload();}}>تأیید صورت تسویه</button></div>}
      <Feedback error={act.error} done={act.done}/>
      <p className="as-note info">تأیید: صورت قفل می‌شود و برای ثبت پرداخت به مالی می‌رود. اعتراض: وضعیت «مورد اعتراض» می‌شود و تا بسته شدن اعتراض، تأیید ممکن نیست.</p>
    </Card>
    {!!s.disputes?.length && <Card title="اعتراض‌های این صورت"><DisputeTable rows={s.disputes}/></Card>}
    <DisputeDialog line={line} agencyId={a.id} sid={s.id} onClose={() => setLine(null)} onDone={() => {setLine(null); q.reload();}}/>
  </>}</Loaded></div>;
}
function OtherLines({s, canAct, onDispute}: {s: Statement; canAct: boolean; onDispute: (l: Line) => void}) {
  const rows = (s.lines ?? []).filter(l => !['SALE', 'REFUND', 'COMMISSION', 'VAT', 'COMMISSION_REVERSAL', 'VAT_REVERSAL'].includes(l.line_type) || !l.reservation_id);
  if (!rows.length) return null;
  return <details className="b2b-more"><summary>ردیف‌های حساب (مانده، واریز، تسویهٔ قبلی، اصلاحیه) · {rows.length.toLocaleString('fa-IR')}</summary>
    <Table rows={rows} rowKey={l => l.id} empty="" cols={[{label: '#', cell: l => l.line_no.toLocaleString('fa-IR')}, {label: 'نوع', cell: l => l.type_label}, {label: 'شرح', cell: l => l.description}, {label: 'مبلغ', cell: l => signed(l.amount_irr)},
      {label: 'اقدام', cell: l => l.open_dispute_id ? <StatusChip status="rejected" label="اعتراض باز"/> : canAct && l.disputable ? <button type="button" className="as-btn ghost" onClick={() => onDispute(l)}>اعتراض</button> : '—'}]}/></details>;
}
const CATS = ['مبلغ کمیسیون', 'ردیف تکراری', 'استرداد ثبت نشده', 'رزرو لغوشده', 'سایر'];
function DisputeDialog({line, agencyId, sid, onClose, onDone}: {line: {id: string; label: string; amount: number} | null; agencyId: string; sid: string; onClose: () => void; onDone: () => void}) {
  const act = useAction(); const [cat, setCat] = useState(CATS[0]); const [amount, setAmount] = useState(''); const [text, setText] = useState('');
  const n = parseRial(amount);
  return <DecisionDialog open={!!line} title={`ثبت اعتراض · ${line?.label ?? ''}`} confirmLabel="ثبت اعتراض" busy={act.busy} error={act.error} onClose={onClose}
    onSubmit={async () => {if (Number.isNaN(n) || n < 0) {act.setError('مبلغ ادعایی را به ریال وارد کنید.'); return;} if (text.trim().length < 20) {act.setError('شرح اعتراض دست‌کم ۲۰ نویسه باشد.'); return;}
      if (await act.run(api => api.post(`/agency/${agencyId}/settlement-statements/${sid}/disputes`, {line_id: line!.id, reason: `${cat}: ${text.trim()}`, claimed_amount_irr: n}))) onDone();}}>
    <Field label="دستهٔ اعتراض"><select value={cat} onChange={e => setCat(e.target.value)}>{CATS.map(c => <option key={c}>{c}</option>)}</select></Field>
    <Field label="مبلغ ادعایی به نفع آژانس (ریال)" hint={<>{!Number.isNaN(n) && n > 0 ? `به حروف: ${amountWords(n)} ریال · ` : ''}سقف: {rial(line?.amount ?? 0)}</>}><input inputMode="numeric" dir="ltr" value={amount} onChange={e => setAmount(e.target.value)}/></Field>
    <Field label="شرح (دست‌کم ۲۰ نویسه)"><textarea rows={4} value={text} onChange={e => setText(e.target.value)}/></Field>
    <Unavail title="پیوست">بارگذاری فایل پس از اتصال ذخیره‌سازی فایل فعال می‌شود؛ فعلاً شمارهٔ سند را در شرح بنویسید.</Unavail>
    <p className="as-muted">پس از ثبت: صورت «مورد اعتراض» می‌شود و کارشناس مالی رسیدگی می‌کند؛ نتیجه (اصلاحیه یا رد با دلیل) در روند صورت دیده می‌شود.</p>
  </DecisionDialog>;
}
function DisputeTable({rows, action}: {rows: Dispute[]; action?: (d: Dispute) => ReactNode}) {
  return <Table rows={rows} rowKey={d => d.id} empty="اعتراضی نیست." cols={[...(rows[0]?.statement_no ? [{label: 'صورت', cell: (d: Dispute) => <span><Ref>{d.statement_no}</Ref><br/><small className="as-muted">{d.agency_name}</small></span>}] : []),
    {label: 'ردیف', cell: d => `${d.line_no?.toLocaleString('fa-IR') ?? '—'} · ${d.line_description ?? ''}`}, {label: 'مبلغ ردیف', cell: d => signed(d.line_amount_irr ?? 0)}, {label: 'ادعا', cell: d => rial(d.claimed_amount_irr)},
    {label: 'شرح', cell: d => d.reason}, {label: 'وضعیت', cell: d => <StatusChip status={d.status === 'accepted' ? 'approved' : d.status === 'rejected' ? 'rejected' : 'under_review'} label={d.status === 'open' ? 'منتظر مالی' : d.status_label}/>},
    {label: 'نتیجه', cell: d => d.resolution_note ? `${d.resolution_note}${d.adjustment_amount_irr ? ` · اصلاحیه ${rial(d.adjustment_amount_irr)}` : ''}` : '—'}, ...(action ? [{label: 'اقدام', cell: action}] : [])]}/>;
}

/* ================================================================ FIN-05 list */
export function FinanceSettlementsPage() {
  const [f, setF] = useState('open'); const q = useLoad<{items: Statement[]; counts: Record<string, number>; open_disputes: number; can_manage: boolean; agencies: Agency[]}>(`/finance/agency-settlements${f ? `?status=${f}` : ''}`);
  const act = useAction(); const router = useRouter(); const today = new Date().toISOString().slice(0, 10); const [form, setForm] = useState({agency_id: '', period_start: today.slice(0, 8) + '01', period_end: today}); const [show, setShow] = useState(false);
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton kind="table"/>}>{d => <>
    <Stats items={[{label: 'پیش‌نویس', value: (d.counts.draft ?? 0).toLocaleString('fa-IR')}, {label: 'منتظر تأیید آژانس', value: (d.counts.issued ?? 0).toLocaleString('fa-IR')},
      {label: 'مورد اعتراض', value: (d.counts.disputed ?? 0).toLocaleString('fa-IR'), hint: `${d.open_disputes.toLocaleString('fa-IR')} اعتراض باز`}, {label: 'تأییدشده · منتظر پرداخت', value: (d.counts.accepted ?? 0).toLocaleString('fa-IR')}]}/>
    <Card title="صورت‌های تسویهٔ آژانس‌ها" action={d.can_manage && <button type="button" className="as-btn" onClick={() => setShow(!show)}>اجرای دورهٔ تسویه</button>}>
      {show && <form className="b2b-grid3" onSubmit={async e => {e.preventDefault(); const r = await act.run(api => api.post<Statement>('/finance/agency-settlements', form), 'پیش‌نویس ساخته شد.'); if (r) {setShow(false); router.push(`/finance/settlements/${r.id}`);}}}>
        <Field label="آژانس"><select required value={form.agency_id} onChange={e => setForm({...form, agency_id: e.target.value})}><option value="">انتخاب کنید</option>{d.agencies.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>
        <DateField label="شروع دوره" value={form.period_start} onChange={v => setForm({...form, period_start: v})} required/>
        <DateField label="پایان دوره" value={form.period_end} onChange={v => setForm({...form, period_end: v})} required/>
        <div className="as-actions"><button className="as-btn" disabled={act.busy}>ساخت پیش‌نویس</button></div></form>}
      <Feedback error={act.error} done={act.done}/>
      <div className="pn-chips b2b-pills" role="group" aria-label="وضعیت">{[['open', 'باز'], ['draft', 'پیش‌نویس'], ['issued', 'منتظر آژانس'], ['disputed', 'مورد اعتراض'], ['accepted', 'منتظر پرداخت'], ['settled', 'تسویه‌شده'], ['', 'همه']].map(([k, l]) => <button key={k || 'all'} type="button" aria-pressed={f === k} onClick={() => setF(k)}>{l}</button>)}</div>
      <Table rows={d.items} rowKey={s => s.id} empty="صورتی در این وضعیت نیست." cols={[{label: 'شمارهٔ صورت', cell: s => <Ref>{s.statement_no}</Ref>}, {label: 'آژانس', cell: s => s.agency_name ?? '—'},
        {label: 'دوره', cell: s => `${jalali(s.period_start)} تا ${jalali(s.period_end)}`}, {label: 'خالص', cell: s => rial(Math.abs(s.net_irr))}, {label: 'جهت', cell: s => dirFa(s.direction)},
        {label: 'وضعیت', cell: s => <SettlementChip status={s.status}/>}, {label: 'مرجع', cell: s => s.settle_reference ? <Ref>{s.settle_reference}</Ref> : '—'},
        {label: 'اقدام', cell: s => <Link className="as-btn ghost" href={`/finance/settlements/${s.id}`}>{s.status === 'draft' ? 'صدور' : s.status === 'disputed' ? 'رسیدگی' : s.status === 'accepted' ? 'ثبت پرداخت' : 'مشاهده'}</Link>}]}/>
      <p className="as-note info">صدور، اصلاحیه و ثبت تسویه با مجوز تسویهٔ مالی ثبت می‌شوند و فقط پس از تأیید کارشناس مالی دوم اعمال می‌شوند. صورت دارای اعتراض باز قابل پرداخت نیست.</p>
    </Card>
    <Card title="اعتراض‌ها و بازگشت به اعتبار"><p><Link className="pn-link" href="/finance/settlements/disputes">صف اعتراض‌های تسویه</Link> · <Link className="pn-link" href="/finance/refunds">صف استرداد (شامل بازگشت به اعتبار آژانس)</Link></p></Card>
  </>}</Loaded></div>;
}

/* ================================================================ FIN-05 detail */
export function FinanceSettlementDetailPage() {const p = useParams<{id: string}>(); return <FinDetail id={String(p?.id ?? '')}/>;}
function FinDetail({id}: {id: string}) {
  const q = useLoad<Statement>(`/finance/agency-settlements/${id}`); const act = useAction();
  const mc = useMine(q.state.kind === 'ready' ? q.state.data.agency_id : undefined, r => r.kind.startsWith('agency.settlement_') && r.payload.settlement_id === id);
  const [bank, setBank] = useState(''); const [adj, setAdj] = useState(''); const [adjReason, setAdjReason] = useState(''); const [confirm, setConfirm] = useState(false); const [note, setNote] = useState('');
  const reload = () => {q.reload(); mc.reload();};
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton/>}>{s => {
    const openDisputes = (s.disputes ?? []).filter(d => d.status === 'open' || d.status === 'adjustment_pending');
    return <>
      <div className="as-card-head"><div><h2>صورت تسویه <Ref>{s.statement_no}</Ref></h2><p className="as-muted">{s.agency_name} · دوره {jalali(s.period_start)} تا {jalali(s.period_end)} · برش {jalali(s.created_at, true)}</p></div><SettlementChip status={s.status}/></div>
      <Stepper status={s.status}/>
      <div className="as-grid2"><Summary s={s}/>
        <Card title="اقدام‌های مالی">
          {mc.reqs.map(r => <div key={r.id} className="as-row"><span>{r.kind === 'agency.settlement_issue' ? 'صدور' : r.kind === 'agency.settlement_settle' ? 'ثبت تسویه' : 'اصلاحیه'}:</span><Approve req={r} onDone={m => {setNote(m); reload();}}/></div>)}
          {note && <p className="as-note ok" role="status">{note}</p>}
          {s.status === 'draft' && s.can_manage && <button type="button" className="as-btn" disabled={act.busy || s.issue_request?.status === 'pending'} onClick={async () => {if (await act.run(api => api.post(`/finance/agency-settlements/${s.id}/issue-request`, {}, newKey('ase-issue')), 'درخواست صدور ثبت شد؛ نفر دوم تأیید می‌کند.')) reload();}}>درخواست صدور (maker)</button>}
          {openDisputes.length > 0 && <p className="as-note bad">{openDisputes.length.toLocaleString('fa-IR')} اعتراض باز · <Link className="pn-link" href="/finance/settlements/disputes">رسیدگی به اختلاف</Link></p>}
          {['issued', 'accepted', 'disputed'].includes(s.status) && s.can_manage && <form className="b2b-section" onSubmit={async e => {e.preventDefault(); const n = Number(adj.replace(/[^\d-]/g, '')); if (!n) {act.setError('مبلغ اصلاحیه را وارد کنید.'); return;}
            if (await act.run(api => api.post(`/finance/agency-settlements/${s.id}/adjustments`, {amount_irr: n, reason: adjReason}, newKey('ase-adj')), 'اصلاحیه ثبت شد؛ نفر دوم تأیید می‌کند.')) {setAdj(''); setAdjReason(''); reload();}}}>
            <h3>صدور اصلاحیه</h3><Field label="مبلغ (ریال؛ منفی = به نفع آژانس)"><input dir="ltr" value={adj} onChange={e => setAdj(e.target.value)}/></Field><Field label="دلیل"><input value={adjReason} onChange={e => setAdjReason(e.target.value)} minLength={5} required/></Field>
            <button className="as-btn ghost" disabled={act.busy}>ثبت اصلاحیه (maker)</button></form>}
          <div className="b2b-section"><h3>ثبت دریافت / تسویه</h3>
            {s.status !== 'accepted' ? <p className="as-muted">{s.status === 'settled' ? `تسویه شد${s.settle_reference ? ` · کد پیگیری ${s.settle_reference}` : ''}.` : 'غیرفعال: صورت باید بدون اعتراض باز و توسط آژانس تأیید شده باشد.'}</p>
              : <><Field label="کد پیگیری بانکی واریز آژانس" hint={s.net_irr > 0 ? 'اجباری؛ به هیچ بانکی ارسال نمی‌شود.' : 'خالص به نفع آژانس است؛ در حساب آژانس به‌صورت اعتبار می‌ماند.'}><input dir="ltr" value={bank} onChange={e => setBank(e.target.value)} disabled={s.net_irr <= 0}/></Field>
                <button type="button" className="as-btn" disabled={act.busy || s.settle_request?.status === 'pending' || (s.net_irr > 0 && bank.trim().length < 4)} onClick={() => setConfirm(true)}>ثبت تسویه (maker)</button></>}</div>
          <Feedback error={act.error} done={act.done}/>
        </Card></div>
      <Card title="ردیف‌ها (نمای مالی)" action={<span className="as-muted">{(s.lines ?? []).length.toLocaleString('fa-IR')} ردیف · فقط افزودنی</span>}>
        <Table rows={s.lines ?? []} rowKey={l => l.id} empty="ردیفی نیست." cols={[{label: '#', cell: l => l.line_no.toLocaleString('fa-IR')}, {label: 'تاریخ', cell: l => jalali(l.occurred_at)}, {label: 'نوع', cell: l => l.type_label},
          {label: 'شرح', cell: l => l.description}, {label: 'نرخ', cell: l => l.vat_rate_bps ? pct(l.vat_rate_bps) : '—'}, {label: 'مبلغ', cell: l => signed(l.amount_irr)},
          {label: 'وضعیت ردیف', cell: l => l.open_dispute_id ? <StatusChip status="rejected" label="مورد اختلاف"/> : <StatusChip status="approved" label="بدون اعتراض"/>}]}/>
      </Card>
      <div className="as-grid2"><StatementTimeline s={s}/>{!!s.disputes?.length && <Card title="اعتراض‌ها"><DisputeTable rows={s.disputes}/></Card>}</div>
      <ConfirmMoney open={confirm} title="ثبت تسویهٔ صورت" amount={Math.abs(s.net_irr)} destination={s.net_irr > 0 ? <>دریافت از {s.agency_name} · کد پیگیری <Ref>{bank}</Ref></> : <>اعتبار حساب {s.agency_name}</>}
        reason={`تسویهٔ صورت ${s.statement_no}`} twoPerson="ثبت شما فقط درخواست است؛ کارشناس مالی دیگری باید تأیید کند." busy={act.busy} error={act.error} confirmLabel="ثبت درخواست تسویه" onClose={() => setConfirm(false)}
        onConfirm={async () => {if (await act.run(api => api.post(`/finance/agency-settlements/${s.id}/settle-request`, s.net_irr > 0 ? {bank_reference: bank.trim()} : {}, newKey('ase-settle')), 'درخواست تسویه ثبت شد؛ نفر دوم تأیید می‌کند.')) {setConfirm(false); reload();}}}/>
    </>;}}</Loaded></div>;
}

/* ================================================================ FIN-08 disputes queue + resolve */
export function FinanceDisputesPage() {
  const [f, setF] = useState('open'); const q = useLoad<{items: Dispute[]; can_manage: boolean}>(`/finance/agency-settlement-disputes?status=${f}`); const [open, setOpen] = useState<Dispute | null>(null); const [note, setNote] = useState('');
  const mc = useMine('x', r => r.kind === 'agency.settlement_adjustment');
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton kind="table"/>}>{d => <>
    <Card title="اعتراض‌های صورت تسویهٔ آژانس‌ها">
      <div className="pn-chips b2b-pills" role="group" aria-label="وضعیت">{[['open', 'باز'], ['closed', 'بسته'], ['all', 'همه']].map(([k, l]) => <button key={k} type="button" aria-pressed={f === k} onClick={() => setF(k)}>{l}</button>)}</div>
      <DisputeTable rows={d.items} action={x => x.status === 'open' && d.can_manage ? <button type="button" className="as-btn" onClick={() => setOpen(x)}>رسیدگی</button>
        : x.status === 'adjustment_pending' ? (mc.reqs.find(r => r.payload.dispute_id === x.id) ? <Approve req={mc.reqs.find(r => r.payload.dispute_id === x.id)!} onDone={m => {setNote(m); q.reload(); mc.reload();}}/> : <span className="as-chip warn">منتظر نفر دوم</span>) : '—'}/>
      {note && <p className="as-note ok" role="status">{note}</p>}
      <p className="as-muted">پذیرش با اصلاحیه یک ردیف «اصلاحیه» تازه می‌سازد (ردیف‌های قبلی تغییر نمی‌کنند) و فقط پس از تأیید کارشناس مالی دوم اعمال می‌شود.</p>
    </Card>
    <Resolve d={open} onClose={() => setOpen(null)} onDone={() => {setOpen(null); q.reload(); mc.reload();}}/>
  </>}</Loaded></div>;
}
function Resolve({d, onClose, onDone}: {d: Dispute | null; onClose: () => void; onDone: () => void}) {
  const act = useAction(); const [mode, setMode] = useState<'accept' | 'reject'>('accept'); const [amt, setAmt] = useState(''); const [reason, setReason] = useState('');
  const n = amt ? parseRial(amt) : d?.claimed_amount_irr ?? 0;
  return <DecisionDialog open={!!d} title={`رسیدگی به اعتراض · ${d?.statement_no ?? ''}`} confirmLabel={mode === 'accept' ? 'ثبت تصمیم و صدور اصلاحیه' : 'ثبت رد'} danger={mode === 'reject'} busy={act.busy} error={act.error} onClose={onClose}
    onSubmit={async () => {if (await act.run(api => api.post(`/finance/agency-settlement-disputes/${d!.id}/resolve`, mode === 'accept' ? {decision: 'accept', adjustment_amount_irr: Number.isNaN(n) ? null : n, reason} : {decision: 'reject', reason}, newKey('asd')))) onDone();}}>
    {d && <dl className="b2b-kv"><dt>ردیف</dt><dd>{d.line_description}</dd><dt>مبلغ ردیف</dt><dd>{signed(d.line_amount_irr ?? 0)}</dd><dt>ادعای آژانس</dt><dd>{rial(d.claimed_amount_irr)}</dd><dt>شرح</dt><dd>{d.reason}</dd></dl>}
    <div className="b2b-choice" role="radiogroup" aria-label="تصمیم"><label><input type="radio" checked={mode === 'accept'} onChange={() => setMode('accept')}/><span>پذیرش با تعدیل<small>ردیف اصلاحیه به نفع آژانس، با تأیید نفر دوم</small></span></label>
      <label><input type="radio" checked={mode === 'reject'} onChange={() => setMode('reject')}/><span>رد با دلیل<small>صورت بدون تغییر می‌ماند</small></span></label></div>
    {mode === 'accept' && <Field label="مبلغ تعدیل (ریال)" hint={!Number.isNaN(n) ? `به حروف: ${amountWords(n)} ریال · صفر = پذیرش بدون اصلاحیه` : ''}><input dir="ltr" inputMode="numeric" placeholder={String(d?.claimed_amount_irr ?? '')} value={amt} onChange={e => setAmt(e.target.value)}/></Field>}
    <Field label={mode === 'accept' ? 'یادداشت برای آژانس' : 'دلیل رد'}><textarea rows={3} required minLength={5} value={reason} onChange={e => setReason(e.target.value)}/></Field>
  </DecisionDialog>;
}

/* ================================================================ FIN-02c refund to agency credit */
type FinRefund = CreditRefund & {title: string; units: number; paid_from_credit_irr: number; refundable_irr: number; free_credit_before_irr: number; free_credit_after_irr: number; maker: string | null; checker: string | null; mc_status: string | null; can_approve: boolean; note: string | null;
  settlement_effect: {commission_bps: number; commission_reversal_irr: number; vat_rate_bps: number; vat_reversal_irr: number; commission_kept_irr: number; vat_kept_irr: number}; destinations: {key: string; label: string; available: boolean; detail: string}[]};
export function FinanceAgencyRefundPage() {const p = useParams<{id: string}>(); return <FinAgencyRefund id={String(p?.id ?? '')}/>;}
function FinAgencyRefund({id}: {id: string}) {
  const q = useLoad<FinRefund>(`/finance/agency-credit-refunds/${id}`); const act = useAction(); const [open, setOpen] = useState(false); const [key] = useState(() => newKey('acr'));
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton/>}>{r => <>
    <div className="as-card-head"><div><h2>بازگشت به اعتبار آژانس · <Ref>{r.booking_reference ?? '—'}</Ref></h2><p className="as-muted">{r.agency_name} · {r.title} · {SOURCE_FA[r.source] ?? r.source} · ثبت {r.maker ?? '—'} · {jalali(r.created_at, true)}</p></div>
      <StatusChip status={r.status === 'executed' ? 'approved' : r.status === 'pending_approval' ? 'under_review' : 'rejected'} label={r.status === 'pending_approval' ? 'منتظر مالی' : r.status_label}/></div>
    <Card title="مقصد استرداد"><p className="as-muted">برای رزرو آژانسی، پیش‌فرض بازگشت به اعتبار آژانس است.</p>
      <div className="b2b-choice" role="radiogroup" aria-label="مقصد">{r.destinations.map(x => <label key={x.key} aria-disabled={!x.available}><input type="radio" name="dest" checked={x.key === 'agency_credit'} disabled={!x.available} readOnly/><span>{x.label}<small>{x.detail}</small></span></label>)}</div></Card>
    <div className="as-grid2"><Card title="تفکیک استرداد به اعتبار" action={<span className="as-muted">واحد: ریال</span>}>
      <dl className="b2b-sum"><div><dt>مبلغ پرداختی آژانس از اعتبار ({r.units.toLocaleString('fa-IR')} مسافر)</dt><dd>{rial(r.paid_from_credit_irr)}</dd></div><div><dt>جریمهٔ لغو</dt><dd>{signed(-r.penalty_irr)}</dd></div>
        <div className="soft"><dt>مبلغ قابل استرداد</dt><dd>{rial(r.refundable_irr)}</dd></div><div><dt>روش</dt><dd>بازگشت به اعتبار آژانس · بدون انتقال بانکی</dd></div>
        <div><dt>ماندهٔ آزاد اعتبار پیش از ثبت</dt><dd>{rial(r.free_credit_before_irr)}</dd></div><div><dt>ماندهٔ آزاد اعتبار پس از ثبت</dt><dd>{rial(r.free_credit_after_irr)}</dd></div></dl>
      <h3>اثر در تسویهٔ دوره</h3>
      <dl className="b2b-sum"><div><dt>برگشت کمیسیون آژانس ({pct(r.settlement_effect.commission_bps)})</dt><dd>{signed(-r.settlement_effect.commission_reversal_irr)}</dd></div><div><dt>برگشت VAT همان کمیسیون ({pct(r.settlement_effect.vat_rate_bps)})</dt><dd>{signed(-r.settlement_effect.vat_reversal_irr)}</dd></div>
        <div><dt>کمیسیون باقی‌مانده روی جریمه + VAT</dt><dd>{rial(r.settlement_effect.commission_kept_irr)} + {rial(r.settlement_effect.vat_kept_irr)}</dd></div></dl>
      <p className="as-muted">همهٔ مبالغ ریال و محاسبهٔ سمت سرور است. ارزش افزوده فقط روی کمیسیون؛ روی مبلغ استرداد VAT نیست.</p></Card>
      <Card title="تأیید بازگشت به اعتبار آژانس">
        <div className="as-amount"><span className="as-muted">مبلغ</span><strong>{rial(r.amount_irr)}</strong><span className="as-muted">به حروف: {amountWords(r.amount_irr)} ریال</span></div>
        <p>مقصد وجه: اعتبار {r.agency_name} · نوع سند <Ref>REFUND</Ref></p>{r.note && <p className="as-muted">دلیل: {r.note}</p>}
        {r.status === 'executed' ? <p className="as-note ok">در دفتر حساب آژانس ثبت شد{r.checker ? ` · تأیید ${r.checker}` : ''} · {jalali(r.executed_at, true)}</p>
          : r.status === 'pending_approval' ? (r.can_approve ? <button type="button" className="as-btn" onClick={() => setOpen(true)}>تأیید و ثبت در اعتبار</button> : <p className="as-note warn">ثبت‌کننده نمی‌تواند تأیید کند؛ کارشناس مالی دیگری (مجوز استرداد) تأیید می‌کند.</p>)
          : <><p className="as-note bad">{r.status_label}</p><button type="button" className="as-btn ghost" disabled={act.busy} onClick={async () => {if (await act.run(api => api.post(`/finance/agency-credit-refunds/${r.id}/requeue`, {}), 'دوباره به صف تأیید رفت.')) q.reload();}}>ارسال دوباره برای تأیید</button></>}
        <Feedback error={act.error} done={act.done}/></Card></div>
    <p className="as-note info">پس از ثبت: ردیف «بازگشت به اعتبار» در دفتر آژانس (حساب و اعتبار) و در صورت تسویهٔ دوره ثبت می‌شود؛ اعلان فقط در پنل و صف رویدادها ثبت می‌شود (پیامکی ارسال نمی‌شود).</p>
    <ConfirmMoney open={open} title="تأیید بازگشت به اعتبار آژانس" amount={r.amount_irr} destination={<>اعتبار {r.agency_name}</>} reason={r.note ?? undefined} idempotencyKey={key} busy={act.busy} error={act.error} confirmLabel="تأیید و ثبت در اعتبار" onClose={() => setOpen(false)}
      twoPerson="شما نفر دوم هستید؛ ثبت‌کننده نمی‌تواند همین درخواست را تأیید کند." onConfirm={async () => {if (await act.run(api => api.post(`/maker-checker/requests/${r.mc_request_id}/approve`, {}), 'در اعتبار آژانس ثبت شد.')) {setOpen(false); q.reload();}}}/>
  </>}</Loaded></div>;
}
/** Card on the finance refund queue: agency-credit refunds waiting for (or past) the finance approval. */
export function AgencyCreditRefundQueue() {
  const q = useLoad<{items: CreditRefund[]}>('/finance/agency-credit-refunds');
  return <div className="as"><Card title="بازگشت به اعتبار آژانس"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton kind="table" rows={2}/>}>{d =>
    <Table rows={d.items} rowKey={r => r.id} empty="بازگشتی به اعتبار آژانس در صف نیست." cols={[{label: 'رزرو', cell: r => <Ref>{r.booking_reference ?? '—'}</Ref>}, {label: 'آژانس', cell: r => r.agency_name ?? '—'}, {label: 'منشأ', cell: r => SOURCE_FA[r.source] ?? r.source},
      {label: 'مبلغ', cell: r => rial(r.amount_irr)}, {label: 'وضعیت', cell: r => <StatusChip status={r.status === 'executed' ? 'approved' : r.status === 'pending_approval' ? 'under_review' : 'rejected'} label={r.status_label}/>},
      {label: 'اقدام', cell: r => <Link className={`as-btn ${r.status === 'pending_approval' ? '' : 'ghost'}`} href={`/finance/refunds/agency-credit/${r.id}`}>{r.status === 'pending_approval' ? 'بررسی و تأیید' : 'مشاهده'}</Link>}]}/>}</Loaded></Card></div>;
}

/* ================================================================ OPS-CH-05 / 05b charter change & cancel */
type Impact = {flight: string; route: string; owner_agency: string | null; agencies: {agency_id: string; agency_name: string | null; allocation_held: number; allocation_initial: number; bookings: number; passengers: number; refundable_to_credit_irr: number}[];
  agency_bookings: number; agency_passengers: number; public_bookings: number; public_passengers: number; passengers_total: number; allocations_held: number; refund_to_agency_credit_irr: number; shift_minutes: number; full_refund_eligible: boolean; old_departure_at: string; new_departure_at: string | null};
type Change = {id: string; kind: string; old_departure_at: string; new_departure_at: string | null; shift_minutes: number; full_refund_eligible: boolean; reason: string; created_at: string; notices: {id: string; status_label: string}[]};
type Block = {id: string; airline_code: string; flight_number: string; origin: string; destination: string; origin_city: string | null; destination_city: string | null; departure_at: string; arrival_at: string; release_at: string; status: string; owner_agency_name?: string; seats: {seats_total: number}};
const localOf = (iso: string) => {const d = new Date(new Date(iso).getTime() + 210 * 60_000); return d.toISOString().slice(0, 16);};
export function OpsCharterChangePage() {const p = useParams<{id: string}>(); return <OpsCharter id={String(p?.id ?? '')}/>;}
function OpsCharter({id}: {id: string}) {
  const list = useLoad<{items: Block[]}>('/staff/charter/blocks'); const hist = useLoad<{items: Change[]; requests: (McReq & {summary: string; payload: {change?: {kind: string; reason: string}}})[]; block_status: string; can_change: boolean}>(`/staff/charter/blocks/${id}/schedule-changes`);
  const block = list.state.kind === 'ready' ? list.state.data.items.find(b => b.id === id) : undefined;
  const [note, setNote] = useState(''); const [kind, setKind] = useState<'change' | 'cancel'>('change'); const [dep, setDep] = useState(''); const [arr, setArr] = useState(''); const [reason, setReason] = useState(''); const [prev, setPrev] = useState<Impact | null>(null); const act = useAction();
  if (list.state.kind !== 'ready' || hist.state.kind !== 'ready') return <div className="as"><Loaded state={list.state.kind !== 'ready' ? list.state : hist.state as never} skeleton={<Skeleton/>}>{() => null}</Loaded></div>;
  if (!block) return <div className="as"><EmptyState title="بلوک یافت نشد">این بلوک در مجموعهٔ شما نیست.</EmptyState></div>;
  const h = hist.state.data; const pending = h.requests.filter(r => r.status === 'pending');
  const body = () => kind === 'cancel' ? {kind, reason} : {kind, reason, new_departure_at: tehranIso(dep), new_arrival_at: tehranIso(arr)};
  const reload = () => {hist.reload(); list.reload();};
  return <div className="as">
    <div className="as-card-head"><div><h2>تغییر برنامهٔ پرواز چارتر</h2><p className="as-muted">بلوک <Ref>{block.airline_code}{block.flight_number}</Ref> · {block.origin_city ?? block.origin} ({block.origin}) ← {block.destination_city ?? block.destination} ({block.destination}) · چارترکننده: {block.owner_agency_name ?? '—'}</p></div>
      <StatusChip status={block.status === 'cancelled' ? 'rejected' : pending.length ? 'under_review' : 'approved'} label={block.status === 'cancelled' ? 'لغوشده' : pending.length ? 'منتظر تأیید نفر دوم' : 'منتشرشده'}/></div>
    {pending.map(r => <p key={r.id} className="as-note warn as-row">{r.summary} — {r.payload.change?.reason}<Approve req={r} onDone={m => {setNote(m); reload();}} label="تأیید و اعمال (نفر دوم)"/></p>)}
    {note && <p className="as-note ok" role="status">{note}</p>}
    {block.status === 'published' && h.can_change && !pending.length && <>
      <div className="pn-chips b2b-pills" role="tablist" aria-label="نوع اقدام">{([['change', 'تغییر زمان یا تاریخ'], ['cancel', 'لغو پرواز']] as const).map(([k, l]) => <button key={k} role="tab" type="button" aria-selected={kind === k} onClick={() => {setKind(k); setPrev(null);}}>{l}</button>)}</div>
      {kind === 'cancel' && <p className="as-note bad">لغو پرواز برگشت‌ناپذیر است: فروش بسته و سهمیه‌ها آزاد می‌شوند، برای رزروهای آژانس بازگشت کامل به اعتبار و برای مسافران مستقیم درخواست لغو در صف عملیات ثبت می‌شود.</p>}
      <div className="as-grid2"><Card title={kind === 'change' ? 'زمان جدید پرواز' : 'لغو پرواز'}>
        <form className="b2b-section" onSubmit={async e => {e.preventDefault(); setPrev(await act.run(api => api.post<Impact>(`/staff/charter/blocks/${id}/schedule-change/preview`, body())) ?? null);}}>
          <div className="b2b-grid"><div className="b2b-box"><small>زمان فعلی</small><b>{jalali(block.departure_at, true)}</b></div>{kind === 'change' && <div className="b2b-box new"><small>زمان جدید</small><b>{dep ? jalali(tehranIso(dep), true) : '—'}</b></div>}</div>
          {kind === 'change' && <div className="b2b-grid"><DateField type="datetime-local" label="حرکت جدید (وقت تهران)" value={dep} onChange={v => {setDep(v); if (!arr && v) setArr(localOf(new Date(new Date(tehranIso(v)).getTime() + (new Date(block.arrival_at).getTime() - new Date(block.departure_at).getTime())).toISOString()));}} required/>
            <DateField type="datetime-local" label="رسیدن جدید (وقت تهران)" value={arr} onChange={setArr} required/></div>}
          <Field label={kind === 'change' ? 'دلیل تغییر و شرح برای آژانس‌ها' : 'دلیل لغو و شرح برای آژانس‌ها'}><textarea rows={3} required minLength={5} value={reason} onChange={e => setReason(e.target.value)}/></Field>
          <button className="as-btn ghost" disabled={act.busy}>پیش‌نمایش اثر</button></form></Card>
        <Card title="پیامد مالی و حق مسافر">
          <p className={`as-note ${kind === 'cancel' ? 'bad' : 'warn'}`}>{kind === 'cancel' ? 'لغو = استرداد کامل بدون جریمه (قاعدهٔ بلوک).' : 'تغییر بیش از ۲ ساعت (یا تغییر روز) طبق قاعدهٔ بلوک «لغو یا تأخیر بیش از ۲ ساعت = استرداد کامل»: آژانس بین پذیرش و استرداد کامل به اعتبار انتخاب می‌کند.'}</p>
          {prev && <dl className="b2b-kv"><dt>جابه‌جایی</dt><dd>{kind === 'cancel' ? 'لغو' : `${prev.shift_minutes.toLocaleString('fa-IR')} دقیقه ${prev.full_refund_eligible ? '· استرداد کامل مجاز' : '· کمتر از قاعده؛ استرداد کامل ندارد'}`}</dd>
            {kind === 'cancel' && <><dt>حداکثر بازگشت به اعتبار آژانس‌ها</dt><dd>{rial(prev.refund_to_agency_credit_irr)}</dd></>}<dt>جریمه برای آژانس یا مسافر</dt><dd>۰</dd></dl>}
          <h3>پیش‌نمایش اعلان</h3><p className="as-row"><span className="as-chip info">اعلان پنل آژانس</span><span className="as-chip">پیامک: پس از اتصال سرویس</span><span className="as-chip">ایمیل: پس از اتصال</span></p>
          <p className="as-muted">اعلان فقط در پنل و صف رویدادها (outbox) ثبت می‌شود؛ در این نسخه هیچ پیامکی ارسال نمی‌شود. اطلاع‌رسانی به مسافران آژانس بر عهدهٔ همان آژانس است.</p></Card></div>
      {prev && <Card title="پیش‌نمایش اثر روی سهمیه‌ها و رزروها" action={<span className="as-muted">محاسبه از سهمیه‌ها و رزروهای فعلی · چیزی ثبت نشده است</span>}>
        <Stats items={[{label: 'آژانس‌های دارای سهمیه یا رزرو', value: prev.agencies.length.toLocaleString('fa-IR')}, {label: 'صندلی سهمیهٔ نگه‌داشته', value: prev.allocations_held.toLocaleString('fa-IR')},
          {label: 'رزروهای متأثر', value: `${(prev.agency_bookings + prev.public_bookings).toLocaleString('fa-IR')} رزرو`, hint: `${prev.public_bookings.toLocaleString('fa-IR')} رزرو مستقیم`}, {label: 'مسافران متأثر', value: `${prev.passengers_total.toLocaleString('fa-IR')} مسافر`}]}/>
        <Table rows={prev.agencies} rowKey={a => a.agency_id} empty="آژانسی سهمیه یا رزرو ندارد." cols={[{label: 'آژانس', cell: a => a.agency_name ?? '—'}, {label: 'سهمیه', cell: a => a.allocation_initial.toLocaleString('fa-IR')},
          {label: 'رزرو متأثر', cell: a => a.bookings.toLocaleString('fa-IR')}, {label: 'مسافر', cell: a => a.passengers.toLocaleString('fa-IR')}, {label: 'صندلی آزاد سهمیه', cell: a => a.allocation_held.toLocaleString('fa-IR')},
          ...(kind === 'cancel' ? [{label: 'بازگشت به اعتبار', cell: (a: Impact['agencies'][number]) => rial(a.refundable_to_credit_irr)}] : []),
          {label: 'اقدام سیستم', cell: a => a.bookings ? (kind === 'cancel' ? 'بازگشت به اعتبار (تأیید مالی) + اعلان' : 'اعلان + فهرست رزروها در پنل آژانس') : 'اعلان'}]}/>
        <div className="as-actions"><button type="button" className={`as-btn ${kind === 'cancel' ? 'danger' : ''}`} disabled={act.busy} onClick={async () => {if (await act.run(api => api.post(`/staff/charter/blocks/${id}/schedule-change`, body(), newKey('csc')), 'درخواست ثبت شد؛ پس از تأیید نفر دوم اعمال می‌شود.')) {setPrev(null); reload();}}}>{kind === 'cancel' ? 'ارسال لغو برای تأیید نفر دوم' : 'ارسال برای تأیید نفر دوم'}</button></div>
        <p className="as-note info">تغییر فقط پس از تأیید نفر دوم (عملیات) اعمال و در سوابق پرواز، بلوک و هر رزرو ثبت می‌شود. هیچ مبلغی بدون تأیید کارشناس مالی جابه‌جا نمی‌شود.</p></Card>}
    </>}
    <Feedback error={act.error} done={act.done}/>
    <Card title="سوابق تغییر و لغو این پرواز"><Table rows={h.items} rowKey={c => c.id} empty="تغییری ثبت نشده است." cols={[{label: 'نوع', cell: c => c.kind === 'cancel' ? 'لغو' : 'تغییر زمان'}, {label: 'قبلی', cell: c => jalali(c.old_departure_at, true)},
      {label: 'جدید', cell: c => c.new_departure_at ? jalali(c.new_departure_at, true) : '—'}, {label: 'جابه‌جایی', cell: c => c.kind === 'cancel' ? '—' : `${c.shift_minutes.toLocaleString('fa-IR')} دقیقه`}, {label: 'دلیل', cell: c => c.reason},
      {label: 'اطلاعیه‌ها', cell: c => c.notices.length.toLocaleString('fa-IR')}, {label: 'ثبت', cell: c => jalali(c.created_at, true)}]}/></Card>
  </div>;
}

/* ================================================================ AG-CH-06 agency notices */
type Notice = {id: string; change_id: string; kind: string; reservation_id: string | null; booking_reference: string | null; passengers: number; seats_held: number; amount_irr: number | null; status: string; status_label: string; flight: string | null; route: string | null;
  old_departure_at: string | null; new_departure_at: string | null; shift_minutes: number | null; full_refund_eligible: boolean; reason: string | null; can_respond: boolean; can_request_refund: boolean; credit_refund: CreditRefund | null; created_at: string};
export function AgencyCharterNoticesPage() {return <AgencyScope>{a => <Notices a={a}/>}</AgencyScope>;}
function Notices({a}: {a: Agency}) {
  const q = useLoad<{items: Notice[]; pending: number}>(`/agency/${a.id}/charter/notices`); const act = useAction(); const [f, setF] = useState('');
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton/>}>{d => {
    const groups = Object.values(d.items.reduce<Record<string, Notice[]>>((g, n) => {(g[n.change_id] ??= []).push(n); return g;}, {}));
    if (!groups.length) return <EmptyState title="اطلاعیه‌ای نیست">تغییر یا لغوی روی پروازهای چارتری که از آن خرید یا سهمیه دارید ثبت نشده است.</EmptyState>;
    return <>{groups.map(g => {const n0 = g[0]; const bookings = g.filter(n => n.reservation_id); const open = bookings.filter(n => n.can_respond); const rows = bookings.filter(n => !f || (f === 'pending' ? n.status === 'pending' : f === 'accepted' ? n.status === 'accepted' : n.status.startsWith('refund')));
      return <section key={n0.change_id} className="as-card b2b-notice">
        <div className="as-card-head"><div><h2>پرواز <Ref>{n0.flight}</Ref> · {n0.kind === 'cancel' ? 'لغو پرواز' : 'تغییر برنامه'}</h2><p className="as-muted">{n0.route} · دلیل: {n0.reason} · اعلام {jalali(n0.created_at, true)}</p></div>
          <StatusChip status={open.length ? 'under_review' : 'approved'} label={open.length ? 'نیازمند پاسخ شما' : 'پاسخ داده شد'}/></div>
        <div className="b2b-grid"><div className="b2b-box"><small>زمان قبلی</small><b>{jalali(n0.old_departure_at, true)}</b></div><div className="b2b-box new"><small>{n0.kind === 'cancel' ? 'وضعیت' : 'زمان جدید'}</small><b>{n0.kind === 'cancel' ? 'لغو شد' : jalali(n0.new_departure_at, true)}</b></div></div>
        <Stats items={[{label: 'رزروهای متأثر', value: `${bookings.length.toLocaleString('fa-IR')} رزرو`, hint: `${bookings.reduce((s, n) => s + n.passengers, 0).toLocaleString('fa-IR')} مسافر`}, {label: 'پاسخ‌داده‌شده', value: `${(bookings.length - open.length).toLocaleString('fa-IR')} از ${bookings.length.toLocaleString('fa-IR')}`},
          {label: 'سهمیهٔ نگه‌داشته', value: g.reduce((s, n) => s + n.seats_held, 0).toLocaleString('fa-IR')}]}/>
        <p className="as-note info">{n0.kind === 'cancel' ? 'لغو: مبلغ همهٔ رزروها بدون جریمه به اعتبار آژانس برمی‌گردد (پس از تأیید مالی). اطلاع‌رسانی به مسافران با شماست.'
          : n0.full_refund_eligible ? 'پذیرش: بلیت با زمان جدید معتبر است. درخواست استرداد: استرداد کامل بدون جریمه به اعتبار آژانس (پس از تأیید مالی)؛ برگشت کمیسیون و VAT در تسویهٔ دوره. اطلاع‌رسانی به مسافران با شماست.'
          : 'جابه‌جایی کمتر از ۲ ساعت است: طبق قاعدهٔ بلوک استرداد کامل ندارد؛ برای استرداد عادی از مسیر لغو و استرداد رزرو اقدام کنید.'}</p>
        {open.length > 0 && <div className="as-actions"><button type="button" className="as-btn" disabled={act.busy} onClick={async () => {for (const n of open) await act.run(api => api.post(`/agency/${a.id}/charter/notices/${n.id}/accept`, {})); q.reload();}}>پذیرش برای {open.length.toLocaleString('fa-IR')} رزرو باقی‌مانده</button></div>}
        {bookings.length > 0 && <><div className="pn-chips b2b-pills" role="group" aria-label="پاسخ">{[['', 'همه'], ['pending', 'منتظر'], ['accepted', 'پذیرفته'], ['refund', 'استرداد']].map(([k, l]) => <button key={k || 'all'} type="button" aria-pressed={f === k} onClick={() => setF(k)}>{l}</button>)}</div>
        <Table rows={rows} rowKey={n => n.id} empty="رزروی در این دسته نیست." cols={[{label: 'کد رزرو', cell: n => <Ref>{n.booking_reference ?? '—'}</Ref>}, {label: 'تعداد', cell: n => n.passengers.toLocaleString('fa-IR')}, {label: 'مبلغ (ریال)', cell: n => rial(n.amount_irr)},
          {label: 'پاسخ', cell: n => <StatusChip status={n.status === 'accepted' || n.status === 'refunded' ? 'approved' : n.status === 'pending' ? 'under_review' : n.status === 'refund_rejected' ? 'rejected' : 'submitted'} label={n.status_label}/>},
          {label: 'اقدام', cell: n => n.can_respond ? <span className="as-row"><button type="button" className="as-btn" disabled={act.busy} onClick={async () => {if (await act.run(api => api.post(`/agency/${a.id}/charter/notices/${n.id}/accept`, {}), 'پذیرش ثبت شد.')) q.reload();}}>پذیرش</button>
            {n.can_request_refund && <button type="button" className="as-btn ghost" disabled={act.busy} onClick={async () => {if (await act.run(api => api.post(`/agency/${a.id}/charter/notices/${n.id}/refund-request`, {}, newKey('ccn')), 'درخواست استرداد ثبت شد؛ پس از تأیید مالی به اعتبار برمی‌گردد.')) q.reload();}}>درخواست استرداد</button>}</span>
            : n.credit_refund ? `به اعتبار: ${rial(n.credit_refund.amount_irr)}` : '—'}]}/></>}
      </section>;})}<Feedback error={act.error} done={act.done}/></>;}}</Loaded></div>;
}
