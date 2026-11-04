'use client';
/* Public voucher check opened from the voucher QR: validity, masked reference, service and status only. */
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {errorOf} from '../panel/PanelKit';

type Result = {valid: boolean; booking_reference: string | null; service: string; status: string; revision: number | null};

export function VoucherCheck({code}: {code: string}) {
  const {api} = useAuth();
  const [r, setR] = useState<Result | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => {api.publicGet<Result>(`/public/vouchers/${encodeURIComponent(code)}`).then(setR).catch(e => setErr(errorOf(e).message));}, [api, code]);
  return <main dir="rtl" className="vc-page">
    <section className={`vc-card ${r ? (r.valid ? 'ok' : 'bad') : ''}`}>
      <p className="vc-brand">کارن تراول — بررسی واچر</p>
      {err ? <><h1>واچر معتبر نیست</h1><p>{err}</p></> : !r ? <p role="status">در حال بررسی…</p> : <>
        <h1>{r.valid ? 'واچر معتبر است' : 'واچر معتبر نیست'}</h1>
        <dl><div><dt>شماره‌ی رزرو</dt><dd dir="ltr">{r.booking_reference ?? '—'}</dd></div><div><dt>خدمت</dt><dd>{r.service}</dd></div><div><dt>وضعیت</dt><dd>{r.status}</dd></div></dl>
        <p className="vc-muted">برای حفظ حریم خصوصی، نام و اطلاعات تماس مسافر نمایش داده نمی‌شود.</p></>}
      <Link href="/">کارن تراول</Link>
    </section>
  </main>;
}
