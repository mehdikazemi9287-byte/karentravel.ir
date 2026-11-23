import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerAccount} from '../../../components/operational/CustomerAccount';
import {CustomerBankAccount} from '../../../components/panel/CommercePanel';
import '../../../components/operational/stitch-account-2026-11.css';
export const metadata = {title: 'پروفایل و مسافران', robots: {index: false}};
/* Stitch _30 (light) / _10 (dark). */
export default function Page() {return <PanelShell area="customer" title="پروفایل و مسافران" intro="مشخصات حساب و مسافرانی که برایشان رزرو می‌کنید."><><CustomerAccount/><CustomerBankAccount/></></PanelShell>;}
