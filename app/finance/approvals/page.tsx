import {PanelShell} from '../../../components/panel/PanelKit';
import {ApprovalsPage} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'تأییدهای دونفره', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="تأییدهای دونفره" intro="درخواست‌هایی که نفر دوم باید تأیید یا رد کند. ثبت‌کننده نمی‌تواند درخواست خودش را تأیید کند."><div className="as"><ApprovalsPage/></div></PanelShell>;}
