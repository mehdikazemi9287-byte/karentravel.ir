'use client';
/* Maker-checker queue (security review H-1): wallet funding, credit-account creation and credit-limit changes
   wait here until a DIFFERENT finance/platform user approves; only then does the ledger move (server-side).
   Lists only what /maker-checker/requests returns for this user; approve/reject buttons only where can_decide. */
import {useState} from 'react';
import {Async, Badge, Card, Table, dateFa, errorOf, money, useLoad} from './PanelKit';

type McRequest = {id: string; kind: string; kind_label: string; status: string; summary: string; amount: number | null; target_ref: string | null;
  maker_user_id: number; created_at: string | null; expires_at: string | null; decision_note: string | null; mine: boolean; can_decide: boolean};

export function FundingApprovals() {
  const [status, setStatus] = useState('pending');
  const {state, reload, api} = useLoad<{items: McRequest[]}>(`/maker-checker/requests?status=${status}`);
  const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  const [busy, setBusy] = useState('');
  async function decide(r: McRequest, approve: boolean) {
    const note = window.prompt(approve ? 'توضیح تأیید (اختیاری)' : 'علت رد درخواست'); if (note === null || busy) return;
    setBusy(r.id); setMsg(null);
    try {await api.post(`/maker-checker/requests/${r.id}/${approve ? 'approve' : 'reject'}`, {note: note || null}); setMsg({ok: true, text: approve ? 'تأیید شد و در دفتر مالی ثبت شد.' : 'درخواست رد شد؛ چیزی ثبت نشد.'}); reload();}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
    finally {setBusy('');}
  }
  return <Card title="درخواست‌های در انتظار تأیید دوم" action={<select value={status} onChange={e => setStatus(e.target.value)} aria-label="وضعیت"><option value="pending">در انتظار تأیید</option><option value="executed">تأیید و اجراشده</option><option value="rejected">ردشده</option><option value="expired">منقضی‌شده</option></select>}>
    <p className="pn-muted">شارژ کیف پول، ایجاد حساب اعتباری و تغییر سقف اعتبار تا تأیید یک کارشناس مالی دیگر اجرا نمی‌شود. درخواست خودتان را نمی‌توانید تأیید کنید.</p>
    {msg && <div className={`pn-note ${msg.ok ? 'ok' : 'error'}`} role={msg.ok ? 'status' : 'alert'}>{msg.text}</div>}
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="درخواستی نیست." cols={[
      {label: 'نوع', cell: r => r.kind_label}, {label: 'شرح', cell: r => r.summary || '—'}, {label: 'مبلغ', cell: r => r.amount === null ? '—' : money(r.amount, 'IRR')},
      {label: 'ثبت', cell: r => `${dateFa(r.created_at)}${r.mine ? ' (شما)' : ''}`}, {label: 'مهلت', cell: r => dateFa(r.expires_at)},
      {label: '', cell: r => r.can_decide ? <span style={{display: 'flex', gap: 6}}><button className="pn-btn" disabled={busy === r.id} onClick={() => decide(r, true)}>تأیید</button><button className="pn-btn ghost" disabled={busy === r.id} onClick={() => decide(r, false)}>رد</button></span> : <Badge status={r.status}/>}]}/>}</Async>
  </Card>;
}
