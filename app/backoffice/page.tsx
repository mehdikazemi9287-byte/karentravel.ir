import Link from 'next/link';
import {PanelShell} from '../../components/panel/PanelKit';
import { ConnectedRolePanel } from '../../components/operational/ConnectedViews';
export default function BackOfficePage(){return <PanelShell area="admin" title="عملیات و پشتیبانی"><div className="journey-main"><Link className="button primary" href="/backoffice/trips">مرکز تغییرات سفر</Link><Link className="button secondary" href="/backoffice/records">رکوردهای عملیاتی</Link><Link className="button secondary" href="/backoffice/booking-requests">درخواست‌های تغییر و استرداد</Link><ConnectedRolePanel kind="backoffice"/></div></PanelShell>}
