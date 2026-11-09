'use client';
/* Customer after-sales pages (spec §2.1, Figma P1): C-01 today, C-02 bookings, C-03 booking detail, C-03a cancel wizard,
   C-04 refunds, C-04a refund timeline, C-06 wallet. Every figure comes from the API (penalty and refundable amount are
   computed by the server); the customer can only request, withdraw a request still waiting, or answer a question. */
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {useMemo, useRef, useState} from 'react';
import {serviceFa, useLoad} from '../PanelKit';
import {DataTable, EmptyState, ErrorState, Loaded, MoneyRows, Ref, Skeleton, StatusChip, Timeline, Unavail, faNum, jDate, jDateTime, messageOf, newKey, toman, type Next, type Step} from './kit';

type Reservation = {id: string; booking_reference: string | null; service_type: string; status: string; price_snapshot?: {total_amount?: number; currency?: string} | null; created_at: string};
type Trip = {id: string; title: string; destination: string | null; starts_at: string | null; status: string};
type Notification = {id: string; title: string; message: string; deep_link: string | null; status: string; created_at: string};
type Wallet = {id: string; currency: string; available: number; reserved: number; consumed: number};
type RefundView = {id: string; status: string; amount: number; destination: string | null; destination_label: string | null; method: string | null; bank_reference: string | null; paid_at: string | null};
export type ServiceRequest = {id: string; request_type: string; request_type_fa: string; status: string; status_fa: string; reason: string | null; created_at: string;
  reservation: {id: string; booking_reference: string | null; service_type: string; status: string};
  quote: {total_amount: number; penalty_amount: number; refundable_amount: number; policy_source: string} | null;
  refund_destination: string | null; refund_destination_label: string | null; penalty_amount: number | null; penalty_source: string | null; approved_amount: number | null;
  decision_reason: string | null; customer_question: string | null; refund: RefundView | null; next: Next; can_withdraw: boolean; can_reply: boolean;
  timeline?: {steps: Step[]; next: Next}};
type Destination = {key: string; label: string; available: boolean; detail: string; sheba_masked?: string; verified?: boolean};
type Options = {reservation_id: string; booking_reference: string | null; status: string; cancellable: boolean; not_cancellable_reason: string | null; open_request_id: string | null;
  policy_verified: boolean; preview: {total_amount: number; penalty_amount: number; refundable_amount: number; paid_amount: number; policy_source: string; computed_at: string; valid_minutes: number} | null;
  requires_review_reason: string | null; destinations: Destination[]};
type ResTimeline = {reservation_id: string; booking_reference: string | null; status: string; steps: {title: string; to_status: string; actor: string; at: string}[]; requests: ServiceRequest[]};

const ACTIVE = new Set(['reserved', 'awaiting_payment', 'confirmed', 'issued', 'changed', 'cancel_requested', 'change_requested', 'refund_requested', 'booking_pending', 'pending']);
const DONE = new Set(['completed']);
const code = (r: {booking_reference: string | null; id: string}) => <Ref>{r.booking_reference ?? r.id.slice(0, 8)}</Ref>;
const daysLeft = (iso: string, now: number) => Math.ceil((new Date(iso).getTime() - now) / 86_400_000);

/* ---------------------------------------------------------------- C-01 today */
export function CustomerToday() {
  const trips = useLoad<Trip[]>('/me/trips'); const reqs = useLoad<{items: ServiceRequest[]}>('/me/service-requests?status=open');
  const res = useLoad<Reservation[]>('/me/reservations'); const wallets = useLoad<Wallet[]>('/me/wallets'); const notes = useLoad<Notification[]>('/me/notifications');
  const [now] = useState(() => Date.now());
  const next = trips.state.kind === 'ready' ? trips.state.data.filter(t => t.starts_at && new Date(t.starts_at).getTime() > now && !/cancel/.test(t.status)).sort((a, b) => (a.starts_at! < b.starts_at! ? -1 : 1))[0] : undefined;
  const tasks: {key: string; level: 'bad' | 'warn' | 'info'; label: string; detail: string; href: string}[] = [];
  if (reqs.state.kind === 'ready') for (const r of reqs.state.data.items) {
    tasks.push({key: r.id, level: r.status === 'needs_customer' || r.next?.overdue ? 'bad' : r.status === 'refund_queued' ? 'info' : 'warn',
      label: `${r.request_type_fa}: ${r.status_fa}`, detail: r.next ? `${r.next.title}${r.next.eta ? ' · تا ' + jDate(r.next.eta) : ''}` : '', href: `/account/refunds/${r.id}`});
  }
  if (res.state.kind === 'ready') for (const r of res.state.data.filter(x => x.status === 'awaiting_payment')) tasks.push({key: r.id, level: 'warn', label: 'پرداخت در انتظار', detail: `رزرو ${r.booking_reference ?? ''}`, href: `/account/bookings/${r.id}`});
  tasks.sort((a, b) => ['bad', 'warn', 'info'].indexOf(a.level) - ['bad', 'warn', 'info'].indexOf(b.level));
  const balance = wallets.state.kind === 'ready' ? wallets.state.data.reduce((s, w) => s + w.available, 0) : null;
  return <div className="as">
    <section className="as-card" aria-labelledby="t-next"><div className="as-card-head"><h2 id="t-next">سفر بعدی</h2><Link className="as-link" href="/account/bookings">همهٔ سفرها و رزروها</Link></div>
      <Loaded state={trips.state} reload={trips.reload} skeleton={<Skeleton rows={2}/>}>{() => next ? <div className="as-row" style={{justifyContent: 'space-between'}}>
        <div><h3>{next.title}{next.destination ? ` — ${next.destination}` : ''}</h3><p className="as-muted">{jDate(next.starts_at)} · {faNum(Math.max(daysLeft(next.starts_at!, now), 0))} روز مانده</p></div>
        <div className="as-row"><StatusChip status={next.status}/><Link className="as-btn ghost" href={`/trips/${next.id}`}>برنامهٔ سفر</Link></div></div>
        : <EmptyState title="سفر پیش رویی ندارید" action={<Link className="as-btn" href="/">جست‌وجوی پرواز، هتل و تور</Link>}/>}</Loaded></section>
    <section className="as-card" aria-labelledby="t-tasks"><h2 id="t-tasks">کارهای منتظر</h2>
      {reqs.state.kind === 'loading' || res.state.kind === 'loading' ? <Skeleton rows={2}/> : reqs.state.kind === 'error' ? <ErrorState status={reqs.state.status} message={reqs.state.message} onRetry={reqs.reload}/>
        : tasks.length === 0 ? <EmptyState title="کار منتظری ندارید">هر درخواست لغو، تغییر یا استرداد با گام بعدی و موعدش اینجا دیده می‌شود.</EmptyState>
        : <div className="as-today">{tasks.slice(0, 4).map(t => <Link key={t.key} className={t.level} href={t.href}><b>{t.label}</b><span className="as-muted">{t.detail}</span></Link>)}</div>}</section>
    <div className="as-grid2">
      <section className="as-card" aria-labelledby="t-notes"><div className="as-card-head"><h2 id="t-notes">آخرین اعلان‌ها</h2><Link className="as-link" href="/account/notifications">همه</Link></div>
        <Loaded state={notes.state} reload={notes.reload} skeleton={<Skeleton rows={3}/>}>{rows => rows.length === 0 ? <EmptyState title="اعلانی ندارید"/> :
          <ul className="as-tl" style={{gap: 4}}>{rows.slice(0, 4).map(n => <li key={n.id}><b>{n.title}</b><small>{jDateTime(n.created_at)}</small><span>{n.message}</span>{n.deep_link?.startsWith('/') && <Link className="as-link" href={n.deep_link}>مشاهده</Link>}</li>)}</ul>}</Loaded></section>
      <section className="as-card" aria-labelledby="t-wallet"><h2 id="t-wallet">کیف پول</h2>
        <Loaded state={wallets.state} reload={wallets.reload} skeleton={<Skeleton rows={1}/>}>{() => <><p style={{fontSize: 22, fontWeight: 800}}>{toman(balance ?? 0)}</p><Link className="as-link" href="/account/wallet">جزئیات و تاریخچه</Link></>}</Loaded></section>
    </div>
  </div>;
}

/* ---------------------------------------------------------------- C-02 bookings */
export function CustomerBookingList() {
  const res = useLoad<Reservation[]>('/me/reservations'); const [tab, setTab] = useState<'active' | 'done' | 'cancelled'>('active'); const [q, setQ] = useState('');
  const group = (s: string) => (ACTIVE.has(s) ? 'active' : DONE.has(s) ? 'done' : 'cancelled');
  return <div className="as"><section className="as-card">
    <div className="as-row" style={{justifyContent: 'space-between'}}>
      <div className="as-tabs" role="tablist" aria-label="گروه رزروها">{([['active', 'فعال و پیش رو'], ['done', 'انجام‌شده'], ['cancelled', 'لغو و استرداد']] as const).map(([k, l]) =>
        <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{res.state.kind === 'ready' ? ` (${faNum(res.state.data.filter(r => group(r.status) === k).length)})` : ''}</button>)}</div>
      <label className="as-field" style={{flex: '0 1 280px'}}>جست‌وجوی کد رزرو<input value={q} onChange={e => setQ(e.target.value)} inputMode="text" placeholder="مثلاً KR-4F8K2Q"/></label>
    </div>
    <Loaded state={res.state} reload={res.reload} skeleton={<Skeleton kind="table" rows={5}/>}>{rows => {
      const shown = rows.filter(r => group(r.status) === tab && (!q || (r.booking_reference ?? r.id).toLowerCase().includes(q.trim().toLowerCase())));
      return shown.length === 0 ? <EmptyState title={q ? 'رزروی با این کد پیدا نشد' : 'در این گروه رزروی ندارید'} action={<Link className="as-btn" href="/">جست‌وجوی سفر</Link>}/> :
        <DataTable caption="رزروهای من" rows={shown} rowKey={r => r.id} cols={[
          {label: 'کد رزرو', cell: r => code(r)}, {label: 'خدمت', cell: r => serviceFa(r.service_type)}, {label: 'تاریخ ثبت', cell: r => jDate(r.created_at)},
          {label: 'مبلغ کل', cell: r => (typeof r.price_snapshot?.total_amount === 'number' ? toman(r.price_snapshot.total_amount) : 'نامشخص')},
          {label: 'وضعیت', cell: r => <StatusChip status={r.status}/>}, {label: '', cell: r => <Link className="as-link" href={`/account/bookings/${r.id}`}>جزئیات و مدیریت</Link>}]}/>;
    }}</Loaded></section></div>;
}

/* ---------------------------------------------------------------- C-03 booking detail */
export function CustomerBookingDetail({id}: {id: string}) {
  const res = useLoad<Reservation & {policy_at_booking?: Record<string, unknown>}>(`/reservations/${id}`); const tl = useLoad<ResTimeline>(`/reservations/${id}/timeline`);
  const opts = useLoad<Options>(`/reservations/${id}/after-sales/options`);
  const pb = useLoad<{total_selling_price: number; service_fee: number | null; discount_amount: number; vat: number; airport_tax: number; i6_tax: number; red_crescent: number; other_taxes: number}>(`/reservations/${id}/price-breakdown`);
  return <div className="as">
    <Loaded state={res.state} reload={res.reload} skeleton={<Skeleton rows={2}/>}>{r => <section className="as-card"><div className="as-card-head">
      <div><h2>رزرو {code(r)}</h2><p className="as-muted">{serviceFa(r.service_type)}{r.created_at ? ` · ثبت ${jDate(r.created_at)}` : ''}</p></div>
      <div className="as-row"><StatusChip status={r.status}/><Link className="as-btn ghost" href={`/manage-booking/${r.id}`}>واچر و مدارک</Link><Link className="as-btn ghost" href={`/contract/${encodeURIComponent(r.id)}`}>قرارداد و فاکتور</Link></div></div></section>}</Loaded>
    <div className="as-grid2">
      <section className="as-card" aria-labelledby="bd-tl"><h2 id="bd-tl">روند رزرو</h2>
        <Loaded state={tl.state} reload={tl.reload} skeleton={<Skeleton kind="timeline"/>}>{t => {
          const open = t.requests.find(x => x.next);
          const steps: Step[] = t.steps.map(s => ({title: s.title, actor: s.actor, at: s.at, to_status: s.to_status}));
          return steps.length === 0 ? <EmptyState title="هنوز رویدادی ثبت نشده است"/> : <Timeline steps={steps} next={open?.next ?? null} followUpHref="/account/support"/>;
        }}</Loaded></section>
      <div style={{display: 'grid', gap: 16}}>
        <section className="as-card" aria-labelledby="bd-actions"><h2 id="bd-actions">لغو، تغییر یا استرداد</h2>
          <Loaded state={opts.state} reload={opts.reload} skeleton={<Skeleton rows={2}/>}>{o => o.open_request_id ? <><p>یک درخواست باز برای این رزرو دارید.</p><Link className="as-btn" href={`/account/refunds/${o.open_request_id}`}>پیگیری درخواست</Link></>
            : o.cancellable ? <><p className="as-muted">{o.policy_verified ? 'جریمه و مبلغ قابل استرداد پیش از ثبت، از قوانین همین رزرو محاسبه و نمایش داده می‌شود.' : o.requires_review_reason}</p>
              <div className="as-actions"><Link className="as-btn" href={`/account/bookings/${id}/cancel`}>درخواست لغو یا استرداد</Link><Link className="as-btn ghost" href={`/account/bookings/${id}/cancel?type=change`}>درخواست تغییر</Link></div></>
            : <p className="as-note warn" role="note">{o.not_cancellable_reason}</p>}</Loaded></section>
        <section className="as-card" aria-labelledby="bd-money"><h2 id="bd-money">تفکیک مبلغ</h2>
          {pb.state.kind === 'error' && pb.state.status === 404 ? <Unavail title="تفکیک مبلغ ثبت نشده است">برای این رزرو جزئیات قیمت از منبع ثبت نشده است؛ مبلغ کل در فهرست رزروها آمده است.</Unavail>
            : <Loaded state={pb.state} reload={pb.reload} skeleton={<Skeleton rows={3}/>}>{b => {
              const taxes = b.vat + b.airport_tax + b.i6_tax + b.red_crescent + b.other_taxes;
              return <MoneyRows label="تفکیک مبلغ پرداختی" lines={[
                ...(taxes ? [{label: 'مالیات و عوارض', value: toman(taxes)}] : []), ...(b.service_fee ? [{label: 'کارمزد خدمات کارن تراول', value: toman(b.service_fee)}] : []),
                ...(b.discount_amount ? [{label: 'تخفیف', value: `− ${toman(b.discount_amount)}`, tone: 'neg' as const}] : []), {label: 'جمع پرداختی', value: toman(b.total_selling_price), tone: 'total'}]}/>;
            }}</Loaded>}</section>
      </div>
    </div>
    <Loaded state={tl.state} reload={tl.reload} skeleton={null}>{t => t.requests.length === 0 ? null : <section className="as-card" aria-labelledby="bd-reqs"><h2 id="bd-reqs">درخواست‌های این رزرو</h2>
      <ul className="as-tl">{t.requests.map(r => <li key={r.id} className={r.status === 'rejected' ? 'bad' : ''}><b>{r.request_type_fa} — {r.status_fa}</b><small>{jDateTime(r.created_at)}</small><Link className="as-link" href={`/account/refunds/${r.id}`}>روند درخواست</Link></li>)}</ul></section>}</Loaded>
  </div>;
}

/* ---------------------------------------------------------------- C-03a cancel wizard (3 steps) */
export function CancelWizard({id, initialType}: {id: string; initialType?: string}) {
  const opts = useLoad<Options>(`/reservations/${id}/after-sales/options`); const router = useRouter();
  const [type, setType] = useState<'cancel' | 'change'>(initialType === 'change' ? 'change' : 'cancel'); const [step, setStep] = useState(1);
  const [reason, setReason] = useState(''); const [dest, setDest] = useState('wallet'); const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const key = useRef(newKey('sr'));
  async function send() {
    if (!opts.api) return; setBusy(true); setError('');
    try {
      const out = await opts.api.post<{id: string}>(`/reservations/${id}/service-requests`, {request_type: type, reason: reason.trim() || null, refund_destination: type === 'cancel' ? dest : null}, key.current);
      router.push(`/account/refunds/${out.id}`);
    } catch (e) {setError(messageOf(e)); setBusy(false);}
  }
  const labels = ['نوع درخواست', type === 'cancel' ? 'پیش‌نمایش جریمه' : 'شرح تغییر', type === 'cancel' ? 'مقصد وجه و تأیید' : 'تأیید'];
  return <div className="as"><Loaded state={opts.state} reload={opts.reload} skeleton={<Skeleton rows={4}/>}>{o => !o.cancellable ? <section className="as-card">
    <p className="as-note warn" role="note">{o.not_cancellable_reason}</p>{o.open_request_id ? <Link className="as-btn" href={`/account/refunds/${o.open_request_id}`}>پیگیری درخواست باز</Link> : <Link className="as-btn ghost" href={`/account/bookings/${id}`}>بازگشت به رزرو</Link>}</section>
    : <section className="as-card" aria-labelledby="wz-title">
      <div className="as-card-head"><h2 id="wz-title">درخواست برای رزرو <Ref>{o.booking_reference ?? id.slice(0, 8)}</Ref></h2></div>
      <ol className="as-steps" aria-label="مراحل">{labels.map((l, i) => <li key={l} className={i + 1 < step ? 'done' : ''} aria-current={i + 1 === step ? 'step' : undefined}>{faNum(i + 1)}. {l}</li>)}</ol>
      {step === 1 && <fieldset className="as-choice" style={{border: 0, padding: 0, margin: 0}}><legend className="as-muted">چه درخواستی دارید؟</legend>
        <label><input type="radio" name="type" checked={type === 'cancel'} onChange={() => setType('cancel')}/><b>لغو و استرداد وجه</b><small>رزرو لغو می‌شود و مبلغ قابل استرداد طبق قوانین همین رزرو برمی‌گردد.</small></label>
        <label><input type="radio" name="type" checked={type === 'change'} onChange={() => setType('change')}/><b>تغییر رزرو (تاریخ، نام، مسیر)</b><small>کارشناس امکان و هزینهٔ تغییر را بررسی و اعلام می‌کند.</small></label>
      </fieldset>}
      {step === 2 && type === 'cancel' && (o.preview ? <>
        <p className="as-note info" role="note">این مبلغ را سرور از قوانین لغو ثبت‌شده هنگام خرید محاسبه کرده است ({jDateTime(o.preview.computed_at)}). مبلغ نهایی پس از تأیید کارشناس قطعی می‌شود.</p>
        <MoneyRows label="پیش‌نمایش جریمه" lines={[{label: 'مبلغ پرداختی شما', value: toman(o.preview.paid_amount)}, {label: 'جریمهٔ لغو (طبق قوانین)', value: `− ${toman(o.preview.penalty_amount)}`, tone: 'neg'},
          {label: 'مبلغ قابل استرداد', value: toman(o.preview.refundable_amount), tone: 'good'}]}/></>
        : <Unavail title="جریمه پس از بررسی اعلام می‌شود">{o.requires_review_reason}</Unavail>)}
      {step === 2 && type === 'change' && <label className="as-field">چه چیزی باید تغییر کند؟<textarea rows={4} value={reason} onChange={e => setReason(e.target.value)} required minLength={5} aria-describedby="wz-ch-help"/><small id="wz-ch-help">مثلاً «تاریخ رفت به ۱۵ آذر». هزینهٔ تغییر را کارشناس اعلام می‌کند.</small></label>}
      {step === 3 && <>
        {type === 'cancel' && <fieldset className="as-choice" style={{border: 0, padding: 0, margin: 0}}><legend className="as-muted">مبلغ به کجا برگردد؟</legend>
          {o.destinations.map(d => <label key={d.key} aria-disabled={!d.available}><input type="radio" name="dest" value={d.key} disabled={!d.available} checked={dest === d.key} onChange={() => setDest(d.key)}/>
            <b>{d.label}{d.key === 'wallet' ? ' (پیشنهادی)' : ''}</b><small>{d.detail}{d.sheba_masked ? <> · <Ref>{d.sheba_masked}</Ref>{d.verified ? '' : ' · احراز نشده'}</> : null}</small></label>)}
        </fieldset>}
        {type === 'cancel' && <label className="as-field">توضیح (اختیاری)<textarea rows={2} value={reason} onChange={e => setReason(e.target.value)}/></label>}
        <label className="as-check"><input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)}/> {type === 'cancel' ? 'قوانین لغو و مبلغ بالا را خواندم و می‌پذیرم.' : 'درخواست تغییر را ثبت کن.'}</label>
        <p className="as-muted">ثبت درخواست، رزرو را مستقیم تغییر نمی‌دهد؛ کارشناس عملیات آن را بررسی و تأیید یا رد می‌کند.</p>
      </>}
      {error && <p className="as-note bad" role="alert">{error}</p>}
      <div className="as-actions as-sticky">
        {step < 3 ? <button type="button" className="as-btn" disabled={step === 2 && type === 'change' && reason.trim().length < 5} onClick={() => setStep(step + 1)}>ادامه</button>
          : <button type="button" className="as-btn" disabled={!agree || busy} onClick={() => void send()}>{busy ? 'در حال ثبت…' : type === 'cancel' ? 'ثبت درخواست استرداد' : 'ثبت درخواست تغییر'}</button>}
        {step > 1 ? <button type="button" className="as-btn ghost" onClick={() => setStep(step - 1)}>بازگشت</button> : <Link className="as-btn ghost" href={`/account/bookings/${id}`}>انصراف</Link>}
      </div>
    </section>}</Loaded></div>;
}

/* ---------------------------------------------------------------- C-04 refunds */
export function CustomerRefundList() {
  const reqs = useLoad<{items: ServiceRequest[]}>('/me/service-requests'); const res = useLoad<Reservation[]>('/me/reservations');
  return <div className="as">
    <section className="as-card" aria-labelledby="rf-mine"><h2 id="rf-mine">درخواست‌های من</h2>
      <Loaded state={reqs.state} reload={reqs.reload} skeleton={<Skeleton kind="table"/>}>{d => d.items.length === 0 ? <EmptyState title="درخواست لغو یا استردادی ندارید">برای لغو، رزرو را از فهرست پایین باز کنید.</EmptyState> :
        <DataTable caption="درخواست‌های لغو، تغییر و استرداد" rows={d.items} rowKey={r => r.id} cols={[
          {label: 'رزرو', cell: r => code(r.reservation)}, {label: 'نوع', cell: r => r.request_type_fa}, {label: 'وضعیت', cell: r => <StatusChip status={r.status}/>},
          {label: 'مبلغ استرداد', cell: r => (r.refund ? toman(r.refund.amount) : r.approved_amount !== null ? toman(r.approved_amount) : r.quote ? `حدود ${toman(r.quote.refundable_amount)}` : 'پس از بررسی')},
          {label: 'مقصد', cell: r => r.refund_destination_label ?? '—'}, {label: 'گام بعدی', cell: r => r.next ? <span>{r.next.title}{r.next.eta ? <small className="as-muted"> · تا {jDate(r.next.eta)}</small> : null}{r.next.overdue ? <> <StatusChip status="failed" label="تأخیر"/></> : null}</span> : '—'},
          {label: '', cell: r => <Link className="as-link" href={`/account/refunds/${r.id}`}>روند درخواست</Link>}]}/>}</Loaded></section>
    <section className="as-card" aria-labelledby="rf-can"><h2 id="rf-can">رزروهای قابل لغو</h2>
      <Loaded state={res.state} reload={res.reload} skeleton={<Skeleton rows={2}/>}>{rows => {const list = rows.filter(r => ['reserved', 'awaiting_payment', 'confirmed', 'issued'].includes(r.status));
        return list.length === 0 ? <EmptyState title="رزرو فعالی برای لغو ندارید"/> : <ul className="as-tl">{list.map(r => <li key={r.id}><b>{serviceFa(r.service_type)} · {code(r)}</b><small>{jDate(r.created_at)}</small><Link className="as-link" href={`/account/bookings/${r.id}/cancel`}>مشاهدهٔ شرایط و درخواست لغو</Link></li>)}</ul>;}}</Loaded></section>
    <Unavail title="پرداخت‌های ناموفق (کسر وجه بدون رزرو)">فهرست جداگانهٔ این پرداخت‌ها هنوز ساخته نشده است؛ اگر وجهی کسر شده و رزرو ثبت نشده، از «پشتیبانی» پیگیری کنید.</Unavail>
  </div>;
}

/* ---------------------------------------------------------------- C-04a refund timeline */
export function CustomerRefundDetail({id}: {id: string}) {
  const st = useLoad<ServiceRequest>(`/me/service-requests/${id}`); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const replyKey = useRef(newKey('reply'));
  async function withdraw() {setBusy(true); setError(''); try {await st.api.post(`/me/service-requests/${id}/withdraw`, {}, newKey('withdraw')); st.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}}
  async function reply() {setBusy(true); setError(''); try {await st.api.post(`/me/service-requests/${id}/reply`, {message: msg.trim()}, replyKey.current); replyKey.current = newKey('reply'); setMsg(''); st.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}}
  return <div className="as"><Loaded state={st.state} reload={st.reload} skeleton={<><Skeleton rows={2}/><Skeleton kind="timeline"/></>}>{r => <>
    <section className="as-card"><div className="as-card-head"><div><h2>درخواست {r.request_type_fa}</h2><p className="as-muted">رزرو {code(r.reservation)} · ثبت {jDateTime(r.created_at)}</p></div><StatusChip status={r.status}/></div>
      <dl className="as-dl">
        {r.request_type !== 'change' && <><dt>مبلغ قابل استرداد</dt><dd>{r.refund ? toman(r.refund.amount) : r.approved_amount !== null ? toman(r.approved_amount) : r.quote ? `${toman(r.quote.refundable_amount)} (پیش‌نمایش)` : 'پس از بررسی کارشناس'}</dd></>}
        {r.penalty_amount !== null && <><dt>جریمه</dt><dd>{toman(r.penalty_amount)}{r.penalty_source === 'manual' ? ' (اعلام کارشناس)' : ' (طبق قوانین لغو)'}</dd></>}
        {r.refund_destination_label && <><dt>مقصد وجه</dt><dd>{r.refund_destination_label}</dd></>}
        {r.refund?.bank_reference && <><dt>کد پیگیری بانکی</dt><dd><Ref>{r.refund.bank_reference}</Ref></dd></>}
        {r.refund?.paid_at && r.refund.status === 'succeeded' && <><dt>تاریخ پرداخت</dt><dd>{jDateTime(r.refund.paid_at)}</dd></>}
        {r.decision_reason && <><dt>توضیح کارشناس</dt><dd>{r.decision_reason}</dd></>}
      </dl>
      {r.can_withdraw && <div className="as-actions"><button type="button" className="as-btn danger" disabled={busy} onClick={() => void withdraw()}>انصراف از درخواست</button><span className="as-muted">تا وقتی بررسی شروع نشده، می‌توانید درخواست را پس بگیرید.</span></div>}
    </section>
    {r.can_reply && <section className="as-card" aria-labelledby="rq-q"><h2 id="rq-q">کارشناس از شما پرسیده است</h2><p className="as-note warn">{r.customer_question}</p>
      <label className="as-field">پاسخ شما<textarea rows={3} value={msg} onChange={e => setMsg(e.target.value)}/></label>
      <div className="as-actions"><button type="button" className="as-btn" disabled={busy || msg.trim().length < 2} onClick={() => void reply()}>ارسال پاسخ</button></div></section>}
    {error && <p className="as-note bad" role="alert">{error}</p>}
    <section className="as-card" aria-labelledby="rq-tl"><h2 id="rq-tl">روند درخواست</h2>{r.timeline && <Timeline steps={r.timeline.steps} next={r.timeline.next} followUpHref="/account/support"/>}</section>
  </>}</Loaded></div>;
}

/* ---------------------------------------------------------------- C-06 wallet */
type History = {wallet_id: string; available: number; reserved: number; consumed: number; items: {id: string; label: string; amount: number; direction: 'in' | 'out'; booking_reference: string | null; at: string}[]};
function WalletHistory({id}: {id: string}) {
  const h = useLoad<History>(`/me/wallets/${id}/history`);
  return <Loaded state={h.state} reload={h.reload} skeleton={<Skeleton kind="table" rows={3}/>}>{d => d.items.length === 0 ? <EmptyState title="هنوز تراکنشی ندارید">واریز استرداد و خرید از کیف پول اینجا ثبت می‌شود.</EmptyState> :
    <DataTable caption="تاریخچهٔ کیف پول" rows={d.items} rowKey={x => x.id} cols={[{label: 'تاریخ', cell: x => jDateTime(x.at)}, {label: 'شرح', cell: x => x.label},
      {label: 'رزرو', cell: x => (x.booking_reference ? <Ref>{x.booking_reference}</Ref> : '—')}, {label: 'مبلغ', cell: x => <span style={{color: x.direction === 'in' ? 'var(--pn-ok)' : 'inherit', fontWeight: 700}}>{x.direction === 'in' ? '+' : '−'} {toman(x.amount)}</span>}]}/>}</Loaded>;
}
export function CustomerWalletPage() {
  const w = useLoad<Wallet[]>('/me/wallets'); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const total = useMemo(() => (w.state.kind === 'ready' ? w.state.data.reduce((s, x) => s + x.available, 0) : 0), [w.state]);
  async function create() {setBusy(true); setError(''); try {await w.api.post('/me/wallets', {currency: 'IRR'}, newKey('wallet')); w.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}}
  return <div className="as"><Loaded state={w.state} reload={w.reload} skeleton={<Skeleton rows={3}/>}>{rows => rows.length === 0 ? <section className="as-card">
    <EmptyState title="کیف پول ندارید">موجودی کیف پول فقط از تراکنش‌های واقعی (مثل استرداد) ساخته می‌شود.</EmptyState>
    <div className="as-actions"><button type="button" className="as-btn" disabled={busy} onClick={() => void create()}>ایجاد کیف پول ریالی</button></div>{error && <p className="as-note bad" role="alert">{error}</p>}</section> : <>
    <section className="as-card" aria-labelledby="wl-bal"><h2 id="wl-bal">موجودی</h2><p style={{fontSize: 28, fontWeight: 800, color: 'var(--pn-plum)'}}>{toman(total)}</p>
      {rows.map(x => <dl key={x.id} className="as-dl"><dt>قابل استفاده</dt><dd>{toman(x.available)}</dd><dt>رزروشده برای خرید</dt><dd>{toman(x.reserved)}</dd></dl>)}
      <div className="as-actions"><button type="button" className="as-btn" disabled aria-disabled="true" aria-describedby="wl-topup">شارژ آنلاین</button></div>
      <p id="wl-topup" className="as-muted">شارژ آنلاین کیف پول هنوز به درگاه پرداخت وصل نشده است؛ واریز بانکی را از بخش «درخواست‌های خزانه» پایین همین صفحه ثبت کنید تا واحد مالی بررسی و اعمال کند.</p></section>
    <section className="as-card" aria-labelledby="wl-hist"><h2 id="wl-hist">تاریخچهٔ تراکنش‌ها</h2>{rows.map(x => <WalletHistory key={x.id} id={x.id}/>)}</section></>}</Loaded></div>;
}
