import { JourneyShell } from '../../components/journey/JourneyShell';
import { TripRequestForm } from '../../components/customer/TripRequestForm';
import { HelpHero, HelpPaths, HelpFaq } from '../../components/customer/HelpCenter';

export default function ContactPage(){
  return <JourneyShell><main className="journey-main hc-page">
    <HelpHero kicker="همراه شما در مسیر سفر" title="تماس با کارن تراول" lead="برای راهنمایی انتخاب خدمت، بررسی امکان رزرو یا پیگیری درخواست، با شمارهٔ پشتیبانی تماس بگیرید یا درخواستت را ثبت کن."/>
    <section className="hc-section" aria-label="ثبت درخواست سفر"><TripRequestForm/></section>
    <HelpPaths/>
    <HelpFaq/>
  </main></JourneyShell>;
}
