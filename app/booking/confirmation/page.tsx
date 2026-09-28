import Link from 'next/link';
import { Shell } from '../../page';
import { ContactOptions } from '../../../components/customer/CustomerHelp';
export default function ConfirmationPage(){return <Shell><section className="container customer-page"><h1>پیگیری تأیید رزرو</h1><p>باز شدن این صفحه به‌تنهایی تأیید خرید نیست. وضعیت رزرو و مدارک را از حساب خود بررسی کنید.</p><Link className="button primary" href="/trips">مشاهده رزروهای من</Link><ContactOptions/></section></Shell>}
