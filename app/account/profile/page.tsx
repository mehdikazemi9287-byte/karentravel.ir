import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerAccount} from '../../../components/operational/CustomerAccount';
export const metadata = {title: 'پروفایل و مسافران | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="پروفایل و مسافران" intro="مشخصات حساب و مسافرانی که برایشان رزرو می‌کنید."><CustomerAccount/></PanelShell>;}
