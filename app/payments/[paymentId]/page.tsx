import { notFound } from 'next/navigation';
import { JourneyShell } from '../../../components/journey/JourneyShell';
import { PaymentReturn } from '../../../components/operational/PaymentReturn';
export const metadata={title:'نتیجهٔ پرداخت | کارن‌سیر',robots:{index:false,follow:false}};
export default async function Page({params}:{params:Promise<{paymentId:string}>}){const {paymentId}=await params;if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(paymentId))notFound();return <JourneyShell><PaymentReturn paymentId={paymentId}/></JourneyShell>}
