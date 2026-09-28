'use client';

import { useCallback, useEffect, useState } from 'react';
import { ErrorState } from './ConnectedViews';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError } from '../../lib/api/karenseir-client';

type OrgCredit = { id: string; organization_id: string; currency: string; available: number; limit_amount?: number; reserved?: number; consumed?: number };
type Wallet = { id: string; currency: string; available: number; reserved: number; consumed: number };
type Reservation = { id: string; booking_reference?: string | null; status: string; service_type: string };
type ApprovalWorkflow = { id: string; reservation_id: string; status: string; current_step_order: number; rejection_reason?: string | null; created_at: string };
type Notice = { id: string; title: string; message: string; deep_link?: string | null; status: string };
type Data = { credit: OrgCredit[]; wallets: Wallet[]; reservations: Reservation[]; approvals: ApprovalWorkflow[]; notifications: Notice[] };

const faMoney = (n: number, c = 'IRR') => `${(n ?? 0).toLocaleString('fa-IR')} ${c === 'IRR' ? 'ریال' : c}`;
const messageOf = (e: unknown) => (e instanceof ApiError ? e.message : 'خطای پیش‌بینی‌نشده رخ داد.');
const WF_LABEL: Record<string, string> = { pending: 'در انتظار تأیید', approved: 'تأییدشده', rejected: 'ردشده' };

export function EmployeePortal() {
  const { api, session } = useAuth();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  const load = useCallback(async () => {
    const v = await Promise.all([
      api.get<OrgCredit[]>('/me/organization-credit'),
      api.get<Wallet[]>('/me/wallets'),
      api.get<Reservation[]>('/me/reservations'),
      api.get<ApprovalWorkflow[]>('/me/approval-workflows'),
      api.get<Notice[]>('/me/notifications'),
    ]);
    return { credit: v[0], wallets: v[1], reservations: v[2], approvals: v[3], notifications: v[4] };
  }, [api]);

  useEffect(() => {
    if (!session) return;
    let active = true;
    load().then(d => active && setData(d)).catch(e => {
      if (!active) return;
      setError(e instanceof ApiError ? { status: e.status, message: e.message } : { status: 0, message: messageOf(e) });
    });
    return () => { active = false; };
  }, [load, session]);

  if (!session) return <ErrorState status={401} message="برای ادامه وارد حساب شوید."/>;
  if (error) return <div className="dashboard container"><div role="alert" className="rounded-2xl bg-rose-50 p-6 text-rose-700">خطای {error.status}: {error.message}</div></div>;
  if (!data) return <div className="dashboard container"><div role="status" className="my-8 animate-pulse rounded-2xl bg-white p-8 text-center text-slate-600">در حال دریافت اطلاعات معتبر…</div></div>;

  const totalCredit = data.credit.reduce((s, c) => s + (c.available ?? 0), 0);
  return (
    <div className="dashboard container">
      <div className="dashboard-title"><div>
        <span className="eyebrow">پنل کارمند · داده احرازشده سازمان</span>
        <h1>اعتبار، درخواست‌های سفر و تأییدها</h1>
        <p>اعتبار سازمانی، کیف پول و وضعیت تأیید درخواست‌های شما مستقیماً از API مجاز همان tenant دریافت می‌شود.</p>
      </div></div>

      <a className="button secondary" href="/organization/requests">درخواست سفر و مزایای سازمانی</a>
      <section className="metrics">
        <div><small>اعتبار سازمانی قابل استفاده</small><strong>{faMoney(totalCredit)}</strong><span>{data.credit.length ? 'مانده واقعی از ledger' : 'حساب اعتبار سازمانی تخصیص نیافته است'}</span></div>
        <div><small>کیف پول شخصی</small><strong>{faMoney(data.wallets.reduce((s, w) => s + w.available, 0))}</strong><span>{data.wallets.length ? `${data.wallets.length} کیف پول` : 'کیف پولی ندارید'}</span></div>
        <div><small>درخواست‌های در انتظار تأیید</small><strong>{data.approvals.filter(a => a.status === 'pending').length.toLocaleString('fa-IR')}</strong><span>از مجموع {data.approvals.length.toLocaleString('fa-IR')} گردش</span></div>
      </section>

      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel-head"><h3>درخواست‌های سفر من</h3></div>
          {data.reservations.length === 0
            ? <p className="mt-3 text-sm text-slate-600">درخواست سفری ثبت نکرده‌اید.</p>
            : data.reservations.slice(0, 8).map(r => {
                const wf = data.approvals.find(a => a.reservation_id === r.id);
                return <div className="mt-3 flex items-center justify-between rounded-xl bg-slate-50 p-3" key={r.id}>
                  <span><b className="block">{r.booking_reference || r.id}</b><small className="text-slate-600">{r.service_type} · {r.status}</small></span>
                  {wf && <span className={`rounded-full px-3 py-1 text-xs ${wf.status === 'approved' ? 'bg-emerald-100 text-emerald-700' : wf.status === 'rejected' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'}`}>{WF_LABEL[wf.status] || wf.status}{wf.status === 'pending' ? ` · مرحله ${wf.current_step_order.toLocaleString('fa-IR')}` : ''}</span>}
                </div>;
              })}
        </article>
        <article className="panel">
          <div className="panel-head"><h3>اعتبار سازمانی به تفکیک حساب</h3></div>
          {data.credit.length === 0
            ? <p className="mt-3 text-sm text-slate-600">حساب اعتبار سازمانی برای شما تعریف نشده است.</p>
            : data.credit.map(c => <div className="mt-3 rounded-xl bg-slate-50 p-3" key={c.id}>
                <b className="block">{faMoney(c.available, c.currency)}</b>
                <small className="text-slate-600">حساب {c.id.slice(0, 8)} · {typeof c.limit_amount === 'number' ? `سقف ${faMoney(c.limit_amount, c.currency)}` : 'سقف نامشخص'}</small>
              </div>)}
        </article>
      </section>

      <section className="panel mt-5">
        <div className="panel-head"><h3>اعلان‌های من</h3></div>
        {data.notifications.length === 0
          ? <p className="mt-3 text-sm text-slate-600">اعلانی ندارید.</p>
          : data.notifications.slice(0, 6).map(n => <div className="mt-3 rounded-xl bg-slate-50 p-3" key={n.id}>
              <b className="block">{n.title}</b><small className="text-slate-600">{n.message}</small>
            </div>)}
      </section>
    </div>
  );
}
