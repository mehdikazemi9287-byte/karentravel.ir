import Link from 'next/link';
import { Shell } from '../../page';
import { ContactOptions } from '../../../components/customer/CustomerHelp';
import '../../../components/operational/stitch-account-2026-11.css';
/* Stitch _12 layout (status hero). This page carries no booking data, so it keeps the honest wording: opening it is not
   a purchase confirmation. The real result lives on /payments/[id] and in «سفرهای من». */
export default function ConfirmationPage(){return <Shell><section className="container customer-page sa-confirm"><div className="sa-result"><span className="sa-result-ic" aria-hidden="true">⌛</span><span className="sa-result-kicker">پیگیری رزرو کارن تراول</span><h1>پیگیری تأیید رزرو</h1><p>باز شدن این صفحه به‌تنهایی تأیید خرید نیست. وضعیت رزرو و مدارک را از حساب خود بررسی کنید.</p><dl className="sa-strip"><div><dt>گام ۱</dt><dd>نتیجهٔ پرداخت را در رسید پرداخت ببینید</dd></div><div><dt>گام ۲</dt><dd>وضعیت رزرو را در «سفرهای من» دنبال کنید</dd></div><div><dt>گام ۳</dt><dd>واچر یا بلیت پس از صدور در جزئیات رزرو</dd></div></dl><div className="sa-actions"><Link className="sa-btn" href="/trips">مشاهده رزروهای من</Link><Link className="sa-btn ghost" href="/account/payments">پرداخت‌ها و رسیدها</Link></div></div><div className="sa-help"><ContactOptions/></div></section></Shell>}
