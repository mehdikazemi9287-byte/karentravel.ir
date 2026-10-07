import {PanelShell} from '../../../components/panel/PanelKit';
import {EnterpriseWorkspace} from '../../../components/operational/EnterpriseWorkspace';
export const metadata = {title: 'درخواست و تأیید سفر | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="درخواست و تأیید سفر" intro="ثبت درخواست مأموریت و سفر، سنجش با سیاست سازمان و تأیید."><EnterpriseWorkspace/></PanelShell>;}
