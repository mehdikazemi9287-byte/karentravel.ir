import {PanelShell} from '../../../components/panel/PanelKit';
import { TourReference } from '../../../components/operational/PanelViews';
export const metadata = {title: 'تورهای مرجع', robots: {index: false}};
export default function Page(){return <PanelShell area="admin" title="تورها"><TourReference/></PanelShell>}
