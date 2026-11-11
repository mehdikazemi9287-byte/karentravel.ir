import {PanelShell} from '../../../components/panel/PanelKit';
import {StaffCharterBlocks} from '../../../components/panel/b2b/StaffB2B';
export const metadata = {title: 'بلوک‌های چارتر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="بلوک‌های چارتر" intro="بازبینی و انتشار بلوک‌های صندلی آژانس‌ها و سقف قیمت سازمان هواپیمایی."><StaffCharterBlocks/></PanelShell>;}
