import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerDocuments} from '../../../components/panel/TravellerDocumentsPanel';
export const metadata = {title: 'مدارک مسافران', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="مدارک مسافران" intro="گذرنامه، کارت ملی، ویزا و عکس مسافران را برای کارشناس عملیات بفرستید؛ بعد از مهلت نگهداری خودکار حذف می‌شوند."><CustomerDocuments/></PanelShell>;}
