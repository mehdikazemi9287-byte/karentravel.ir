import {PanelShell} from '../../../../components/panel/PanelKit';
import {CharterFlightsPage} from '../../../../components/panel/b2b/Charter';
export const metadata = {title: 'پرواز و بلوک صندلی', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="پرواز و بلوک صندلی" intro="ثبت پرواز و چارتر نیازمند مجوز معتبر بند الف است. منبع موجودی: ورود دستی یا شناسهٔ سامانهٔ بیرونی پس از قرارداد."><CharterFlightsPage/></PanelShell>;}
