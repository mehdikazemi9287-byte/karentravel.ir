import { JourneyShell } from '../../../components/journey/JourneyShell';
import { OfferDetail } from '../../../components/operational/OfferDetail';
export const metadata={title:'جزئیات و انتخاب خدمت | کارن‌سیر',robots:{index:false,follow:false}};
export default async function Page({params}:{params:Promise<{offerId:string}>}){const {offerId}=await params;return <JourneyShell><OfferDetail offerId={offerId}/></JourneyShell>}
