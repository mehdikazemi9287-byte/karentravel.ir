'use client';
import Link from 'next/link';
import {useAuth} from '../../lib/api/auth-context';
import {roleLinks} from '../../lib/role-navigation';
import './approved-figma.css';
import {ApprovedEcosystemServices} from './ApprovedEcosystemServices';
import {ApprovedHomeLower, ApprovedFooterLight, ApprovedHomeHero, ApprovedHomeBento} from './ApprovedHomeLower';
import {Suspense, type ReactNode} from 'react';
import {HomeSearchExperience} from '../search/HomeSearchExperience';
import {supportPhone} from '../../lib/site-contact';
const imgIconInstagram = "/images/approved-figma/imgIconInstagram.svg";
const imgIconTelegram = "/images/approved-figma/imgIconTelegram.svg";
const imgIconLinkedIn = "/images/approved-figma/imgIconLinkedIn.svg";
const imgComponentLogoMark = "/images/approved-figma/imgComponentLogoMark.svg";
const imgIconDot = "/images/approved-figma/imgIconDot.svg";
const imgIconPerson = "/images/approved-figma/imgIconPerson.svg";
const imgIconCompare = "/images/approved-figma/imgIconCompare.svg";
const imgIconChevronLeft = "/images/approved-figma/imgIconChevronLeft.svg";
const imgThumb = "/images/approved-figma/imgThumb.jpg";
const imgThumb1 = "/images/approved-figma/imgThumb1.jpg";
const imgHeroImageYazd = "/images/approved-figma/imgHeroImageYazd.jpg";
const imgThumb2 = "/images/approved-figma/imgThumb2.jpg";
const imgThumb3 = "/images/approved-figma/imgThumb3.jpg";
const imgTileQeshm = "/images/approved-figma/imgTileQeshm.jpg";
const imgTileShiraz = "/images/approved-figma/imgTileShiraz.jpg";
const imgTileMasuleh = "/images/approved-figma/imgTileMasuleh.jpg";
const imgTileIsfahan = "/images/approved-figma/imgTileIsfahan.jpg";
const imgImage = "/images/approved-figma/imgImage.jpg";
const imgImage1 = "/images/approved-figma/imgImage1.jpg";
const imgImage2 = "/images/approved-figma/imgImage2.jpg";
const imgIconSupport = "/images/approved-figma/imgIconSupport.svg";
const imgEllipse = "/images/approved-figma/imgEllipse.svg";
const imgIconCheck = "/images/approved-figma/imgIconCheck.svg";
const imgIconArrowLeft = "/images/approved-figma/imgIconArrowLeft.svg";
const imgIconPin = "/images/approved-figma/imgIconPin.svg";
const imgIconPlaneSmall = "/images/approved-figma/imgIconPlaneSmall.svg";
const imgIconPerson1 = "/images/approved-figma/imgIconPerson1.svg";
const imgIconCalendar = "/images/approved-figma/imgIconCalendar.svg";
const imgIconArrowLeft1 = "/images/approved-figma/imgIconArrowLeft1.svg";
const imgCoralDot = "/images/approved-figma/imgCoralDot.svg";
const imgLaptopScreen = "/images/approved-figma/imgLaptopScreen.svg";
const imgTablet = "/images/approved-figma/imgTablet.svg";
const imgIconChart = "/images/approved-figma/imgIconChart.svg";
const imgIconCheck1 = "/images/approved-figma/imgIconCheck1.svg";
const imgIconStaff = "/images/approved-figma/imgIconStaff.svg";

type ComponentSocialIconProps = {
  className?: string;
  platform?: "Instagram" | "Telegram" | "LinkedIn";
};

function ComponentSocialIcon({ className, platform = "Instagram" }: ComponentSocialIconProps) {
  const isLinkedIn = platform === "LinkedIn";
  const isTelegram = platform === "Telegram";
  return (
    <div className={className || "bg-[rgba(255,255,255,0.1)] overflow-clip relative rounded-[17px] size-[34px]"} id={isLinkedIn ? "node-71_71" : isTelegram ? "node-71_70" : "node-71_69"}>
      {platform === "Instagram" && (
        <div className="absolute left-[7px] size-[20px] top-[7px]" data-node-id="68:47" data-name="Icon / Instagram">
          <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconInstagram} />
        </div>
      )}
      {isTelegram && (
        <div className="absolute left-[7px] size-[20px] top-[7px]" data-node-id="68:51" data-name="Icon / Telegram">
          <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconTelegram} />
        </div>
      )}
      {isLinkedIn && (
        <div className="absolute left-[7px] size-[20px] top-[7px]" data-node-id="68:53" data-name="Icon / LinkedIn">
          <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconLinkedIn} />
        </div>
      )}
    </div>
  );
}

function ComponentLogoMark({ className }: { className?: string }) {
  return (
    <div className={className || "relative size-[34px]"} data-node-id="66:46" data-name="Component / Logo Mark">
      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgComponentLogoMark} />
    </div>
  );
}

type ComponentButtonProps = {
  className?: string;
  type?: "Auth" | "SearchCTA" | "Compare" | "OrgSolutions";
};

export function AccountMenu({variant = "site"}: {variant?: "site" | "panel"}) {
  const {session, logout} = useAuth();
  if (!session?.user) return null;
  return <details className={variant === "panel" ? "kh-account-menu pn-account" : "kh-account-menu"} dir="rtl">
    <summary className={variant === "panel" ? "pn-account-label" : "bg-[#ef5b3d] px-[20px] py-[12px] rounded-[100px] text-white font-[Vazirmatn] font-semibold text-[15px]"}>حساب کاربری</summary>
    <div className="kh-account-popover">
      <p>{session.user.name}</p>
      {roleLinks(session.user.role).map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}
      <button type="button" onClick={() => {void logout();}}>خروج از حساب</button>
    </div>
  </details>;
}

function ComponentButton({ className, type = "Auth" }: ComponentButtonProps) {
  const {session} = useAuth();
  const isAuth = type === "Auth";
  const isCompare = type === "Compare";
  const isOrgSolutions = type === "OrgSolutions";
  const isSearchCta = type === "SearchCTA";
  if (isAuth && session?.user) return <AccountMenu/>;
  return (
    <Link href={isAuth?"/login":isCompare?"/compare":isOrgSolutions?"/organization":"/#search"} className={className || `content-stretch flex items-center overflow-clip relative ${isOrgSolutions ? "bg-[#28132b] gap-[8px] px-[22px] py-[14px] rounded-[100px]" : isCompare ? "bg-[#ef5b3d] gap-[8px] px-[22px] py-[14px] rounded-[100px]" : isSearchCta ? "bg-[#ef5b3d] justify-center py-[16px] rounded-[16px] w-[572px]" : "bg-[#ef5b3d] gap-[8px] px-[20px] py-[12px] rounded-[100px]"}`} id={isOrgSolutions ? "node-71_153" : isCompare ? "node-71_152" : isSearchCta ? "node-71_150" : "node-71_149"}>
      {isAuth && (
        <>
          <div className="relative shrink-0 size-[18px]" data-node-id="45:5" data-name="icon-dot">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconDot} />
          </div>
          <div className="relative shrink-0 size-[12px]" data-node-id="68:77" data-name="Icon / Person">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconPerson} />
          </div>
        </>
      )}
      {["Auth", "SearchCTA"].includes(type) && (
        <p className={`[word-break:break-word] leading-[normal] relative shrink-0 text-white whitespace-nowrap ${isSearchCta ? 'font-[Vazirmatn] font-bold text-[16px]' : 'font-[Vazirmatn] font-semibold text-[15px]'}`} dir="auto" id={isSearchCta ? "node-48_35" : "node-45_6"}>
          {isSearchCta ? "پیدا کن" : "ورود / ثبت‌نام"}
        </p>
      )}
      {isCompare && (
        <>
          <div className="relative shrink-0 size-[18px]" data-node-id="67:77" data-name="Icon / Compare">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconCompare} />
          </div>
          <p className="[word-break:break-word] font-[Vazirmatn] font-semibold leading-[normal] relative shrink-0 text-[15px] text-white whitespace-nowrap" dir="auto" data-node-id="53:47">
            مقایسه کن
          </p>
        </>
      )}
      {isOrgSolutions && (
        <>
          <div className="relative shrink-0 size-[16px]" data-node-id="67:80" data-name="Icon / ChevronLeft">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconChevronLeft} />
          </div>
          <p className="[word-break:break-word] font-[Vazirmatn] font-semibold leading-[normal] relative shrink-0 text-[15px] text-white whitespace-nowrap" dir="auto" data-node-id="54:73">
            راهکارهای سازمانی
          </p>
        </>
      )}
    </Link>
  );
}

type ComponentHotelRowProps = {
  className?: string;
  hotel?: "Abbasi" | "Zandiyeh";
};

function ComponentHotelRow({ className, hotel = "Abbasi" }: ComponentHotelRowProps) {
  const isZandiyeh = hotel === "Zandiyeh";
  return (
    <div className={className || "content-stretch flex gap-[16px] items-center overflow-clip relative"} id={isZandiyeh ? "node-71_110" : "node-71_109"}>
      <div className="h-[70px] relative rounded-[16px] shrink-0 w-[90px]" id={isZandiyeh ? "node-53_59" : "node-53_51"} data-name="Thumb">
        <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[16px] size-full" src={isZandiyeh ? imgThumb1 : imgThumb} />
      </div>
      <div className="[word-break:break-word] content-stretch flex flex-col gap-[6px] items-end leading-[normal] overflow-clip relative shrink-0 whitespace-nowrap" id={isZandiyeh ? "node-53_60" : "node-53_52"} data-name="Frame">
        <p className="font-[Vazirmatn] font-semibold relative shrink-0 text-[16px] text-white" dir="auto" id={isZandiyeh ? "node-53_61" : "node-53_53"}>
          {isZandiyeh ? "هتل زندیه شیراز" : "هتل عباسی اصفهان"}
        </p>
        <div className="content-stretch flex gap-[6px] items-center overflow-clip relative shrink-0 text-[13px]" id={isZandiyeh ? "node-53_62" : "node-53_54"} data-name="Frame">
          <p className="font-[Vazirmatn] font-bold relative shrink-0 text-[#ef5b3d]" id={isZandiyeh ? "node-53_63" : "node-53_55"}>
            استعلام قیمت
          </p>
          <p className="font-[Vazirmatn] font-normal relative shrink-0 text-[#f2e5eb]" dir="auto" id={isZandiyeh ? "node-53_64" : "node-53_56"}>
            قیمت پس از استعلام
          </p>
        </div>
      </div>
    </div>
  );
}

type ComponentHeaderNavItemProps = {
  className?: string;
  item?: "About" | "Magazine" | "Services" | "Tour" | "Hotel" | "Train" | "Flight";
};

function ComponentHeaderNavItem({ className, item = "About" }: ComponentHeaderNavItemProps) {
  const isFlight = item === "Flight";
  const isHotel = item === "Hotel";
  const isMagazine = item === "Magazine";
  const isServices = item === "Services";
  const isTour = item === "Tour";
  const isTrain = item === "Train";
  return (
    <Link href={isFlight?"/flights":isTrain?"/trains":isHotel?"/hotels":isTour?"/tours":isServices?"/services":isMagazine?"/travel-guides":"/contact"} className={className || `h-[23px] relative ${["Hotel", "Train", "Flight"].includes(item) ? "w-[27px]" : isTour ? "w-[17px]" : isServices ? "w-[73px]" : isMagazine ? "w-[61px]" : "w-[49px]"}`} id={isFlight ? "node-71_93" : isTrain ? "node-71_92" : isHotel ? "node-71_91" : isTour ? "node-71_90" : isServices ? "node-71_89" : isMagazine ? "node-71_88" : "node-71_87"}>
      <p className="[word-break:break-word] absolute font-[Vazirmatn] font-medium inset-0 leading-[normal] text-[#3a1b3d] text-[15px] whitespace-nowrap" dir="auto" id={isFlight ? "node-45_14" : isTrain ? "node-45_13" : isHotel ? "node-45_12" : isTour ? "node-45_11" : isServices ? "node-45_10" : isMagazine ? "node-45_9" : "node-45_8"}>
        {isFlight ? "پرواز" : isTrain ? "قطار" : isHotel ? "هتل" : isTour ? "تور" : isServices ? "خدمات سفر" : isMagazine ? "مجله سفر" : "درباره ما"}
      </p>
    </Link>
  );
}

export default function ApprovedFigmaHome() {
  return (
    <div className="approved-figma-home bg-[#fbf3e7] content-stretch flex flex-col items-start relative size-full" data-node-id="44:3" data-name="KarenSeir Homepage / Desktop 1440">
      <div className="bg-[#fbf3e7] content-stretch flex flex-col gap-[40px] items-center overflow-clip pb-[64px] pt-[24px] px-[64px] relative shrink-0 w-full" data-node-id="45:2" data-name="Section / Header + Hero">
        <div className="bg-[#fffcf9] content-stretch flex gap-[32px] items-center overflow-clip pl-[14px] pr-[24px] py-[10px] relative rounded-[100px] shadow-[0px_4px_20px_0px_rgba(102,77,51,0.08)] shrink-0 w-full" data-node-id="45:3" data-name="Header / Nav">
          <ComponentButton className="bg-[#ef5b3d] content-stretch flex gap-[8px] items-center overflow-clip px-[20px] py-[12px] relative rounded-[100px] shrink-0" />
          <div className="content-stretch flex flex-[1_0_0] gap-[26px] items-center justify-end min-w-px overflow-clip relative" data-node-id="45:7" data-name="Nav Links">
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[49px]" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[61px]" item="Magazine" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[73px]" item="Services" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[17px]" item="Tour" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[27px]" item="Hotel" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[27px]" item="Train" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[27px]" item="Flight" />
          </div>
          <div className="content-stretch flex gap-[8px] items-center overflow-clip relative shrink-0" data-node-id="45:15" data-name="Logo">
            <ComponentLogoMark className="relative shrink-0 size-[34px]" />
            <p className="[word-break:break-word] font-[Vazirmatn] font-bold leading-[normal] relative shrink-0 text-[#3a1b3d] text-[19px] whitespace-nowrap" dir="auto" data-node-id="45:17">
              <Link href="/" aria-label="کارن سیر، صفحه اصلی">کارن سیر</Link>
            </p>
          </div>
        </div>
        <ApprovedHomeHero search={<div className="approved-search-card" data-node-id="48:10" data-name="Search Card"><Suspense fallback={<p role="status">در حال آماده‌سازی جست‌وجو…</p>}><HomeSearchExperience presentation="approved"/></Suspense></div>}/>
      </div>
      <ApprovedEcosystemServices/>
      <ApprovedHomeBento/>
      <ApprovedHomeLower/>
      <ApprovedFooterLight/>
    </div>
  );
}
export function ApprovedHeader(){return (<div className="bg-[#fffcf9] content-stretch flex gap-[32px] items-center overflow-clip pl-[14px] pr-[24px] py-[10px] relative rounded-[100px] shadow-[0px_4px_20px_0px_rgba(102,77,51,0.08)] shrink-0 w-full" data-node-id="45:3" data-name="Header / Nav">
          <ComponentButton className="bg-[#ef5b3d] content-stretch flex gap-[8px] items-center overflow-clip px-[20px] py-[12px] relative rounded-[100px] shrink-0" />
          <div className="content-stretch flex flex-[1_0_0] gap-[26px] items-center justify-end min-w-px overflow-clip relative" data-node-id="45:7" data-name="Nav Links">
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[49px]" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[61px]" item="Magazine" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[73px]" item="Services" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[17px]" item="Tour" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[27px]" item="Hotel" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[27px]" item="Train" />
            <ComponentHeaderNavItem className="h-[23px] relative shrink-0 w-[27px]" item="Flight" />
          </div>
          <div className="content-stretch flex gap-[8px] items-center overflow-clip relative shrink-0" data-node-id="45:15" data-name="Logo">
            <ComponentLogoMark className="relative shrink-0 size-[34px]" />
            <p className="[word-break:break-word] font-[Vazirmatn] font-bold leading-[normal] relative shrink-0 text-[#3a1b3d] text-[19px] whitespace-nowrap" dir="auto" data-node-id="45:17">
              <Link href="/" aria-label="کارن سیر، صفحه اصلی">کارن سیر</Link>
            </p>
          </div>
        </div>)}
export function ApprovedFooter(){return <ApprovedFooterLight/>}
export function ApprovedShell({children}:{children:ReactNode}){return <div className="approved-site"><div className="approved-shared-header"><ApprovedHeader/></div><main>{children}</main><ApprovedFooter/></div>}
