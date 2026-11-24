/* Offline sales request (Launch V1 item 7): shown on services that have no live supplier yet.
 * Says plainly that online booking is not active, shows no price or availability, and sends the request
 * to the sales desk (TripRequestForm → POST /public/sales-desk/requests). A desk agent calls back with a real quote. */
import {TripRequestForm} from './TripRequestForm';

export function OfflineRequest({service, trip, intro}: {service: string; trip?: string; intro?: string}) {
  return <section className="container customer-page" aria-label={`درخواست ${service}`} data-offline-request="">
    <p role="note"><b>رزرو آنلاین {service} هنوز فعال نیست.</b> قیمت و موجودی آنلاین در سایت نمایش داده نمی‌شود؛ درخواستت را بگذار تا کارشناس فروش گزینه‌ها و قیمت واقعی را تلفنی اعلام کند.</p>
    <TripRequestForm title={`درخواست ${service}`} intro={intro ?? 'مقصد، تاریخ و تعداد مسافران را بنویس. ثبت درخواست به معنی رزرو یا تأیید قیمت نیست.'} initial={{trip: trip ?? service}}/>
  </section>;
}
