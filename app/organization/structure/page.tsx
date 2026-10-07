import {PanelShell} from '../../../components/panel/PanelKit';
import {OrganizationStructure} from '../../../components/operational/OrganizationStructure';
export const metadata = {title: 'واحدها و مراکز هزینه | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="واحدها و مراکز هزینه" intro="ساختار سازمان برای تخصیص درخواست و هزینه."><OrganizationStructure/></PanelShell>;}
