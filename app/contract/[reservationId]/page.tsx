import {PanelShell} from '../../../components/panel/PanelKit';
import {ContractView} from '../../../components/panel/InventoryPanel';
export const metadata = {title: 'قرارداد خرید خدمت | کارن‌سیر', robots: {index: false}};
export default async function Page({params}: {params: Promise<{reservationId: string}>}) {const {reservationId} = await params; return <PanelShell area="customer" title="قرارداد خرید خدمت"><ContractView reservationId={reservationId}/></PanelShell>;}
