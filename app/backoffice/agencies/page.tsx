import {PanelShell} from '../../../components/panel/PanelKit';
import {StaffAgencies} from '../../../components/panel/b2b/StaffB2B';
export const metadata = {title: 'آژانس‌ها و مجوزها', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="آژانس‌ها و مجوزها" intro="آنبوردینگ و احراز مجوز آژانس‌ها در درگاه ملی مجوزها، سامانهٔ وزارت میراث و سامانهٔ سازمان هواپیمایی."><StaffAgencies/></PanelShell>;}
