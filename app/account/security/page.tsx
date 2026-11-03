import {PanelShell} from '../../../components/panel/PanelKit';
import {AccountSecurity} from '../../../components/panel/AccountSecurityPanel';
export const metadata = {title: 'امنیت ورود | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="امنیت ورود" intro="ورود دومرحله‌ای با برنامه‌ی Google Authenticator: بعد از کد پیامکی، کد شش‌رقمی برنامه هم لازم می‌شود."><AccountSecurity/></PanelShell>;}
