import {PanelShell} from '../../../components/panel/PanelKit';
import {SmsCampaigns} from '../../../components/panel/SmsCampaignPanel';
export const metadata = {title: 'کمپین پیامکی', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="کمپین پیامکی" intro="پیامک به مشتریان میز فروش یا اعضای حلقه‌ی همسفران، با لغو اشتراک و وضعیت ارسال واقعی."><SmsCampaigns/></PanelShell>;}
