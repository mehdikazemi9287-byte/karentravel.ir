import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyPricingPage} from '../../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'قواعد markup و کمیسیون', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="قواعد markup و کمیسیون" intro="markup شما برای مشتری خودتان است؛ قیمت مشتری هرگز از سقف سازمان هواپیمایی بالاتر نمی‌رود."><AgencyPricingPage/></PanelShell>;}
