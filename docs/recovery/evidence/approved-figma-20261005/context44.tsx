const imgIconInstagram = "https://www.figma.com/api/mcp/asset/72813c5f-3991-40f4-b50d-075c369be256.svg";
const imgIconTelegram = "https://www.figma.com/api/mcp/asset/c3191352-6171-41e5-a59f-8e713056e6dd.svg";
const imgIconLinkedIn = "https://www.figma.com/api/mcp/asset/79a694c8-ed69-4789-99a0-09dcc612138e.svg";
const imgComponentLogoMark = "https://www.figma.com/api/mcp/asset/fd7dae03-7081-4a59-bba4-adcd531c6953.svg";
const imgIconDot = "https://www.figma.com/api/mcp/asset/c298e023-4bf5-4452-958e-86b59a28d0c0.svg";
const imgIconPerson = "https://www.figma.com/api/mcp/asset/fca62c8b-c51d-4af6-9821-64d6e9584ce2.svg";
const imgIconCompare = "https://www.figma.com/api/mcp/asset/3f6fe6a5-f0ce-4b65-bbbf-6930eed89748.svg";
const imgIconChevronLeft = "https://www.figma.com/api/mcp/asset/ad11c540-aeb9-4f31-9c4c-b96c501f44ef.svg";
const imgThumb = "https://www.figma.com/api/mcp/asset/969db0b7-1e5a-456c-a9c0-fcabb8f7e260.png";
const imgThumb1 = "https://www.figma.com/api/mcp/asset/57e31767-4b5d-4425-876b-82756b8e557f.png";
const imgHeroImageYazd = "https://www.figma.com/api/mcp/asset/e4c2bd39-3a65-4c05-86d8-7aa0dcf3fbb3.png";
const imgThumb2 = "https://www.figma.com/api/mcp/asset/427d34dd-8fd7-4e5a-aee7-7f90e9a8f4c0.png";
const imgThumb3 = "https://www.figma.com/api/mcp/asset/4a0bf7a4-e749-4634-ba16-ba8f2c3e1153.png";
const imgTileQeshm = "https://www.figma.com/api/mcp/asset/e896a508-6f35-4bc0-b0be-cc732c6d264e.png";
const imgTileShiraz = "https://www.figma.com/api/mcp/asset/712b0e5d-6335-4751-a00a-b1224194ee34.png";
const imgTileMasuleh = "https://www.figma.com/api/mcp/asset/b824e7b6-f6e8-41d5-882b-b674c3ca3961.png";
const imgTileIsfahan = "https://www.figma.com/api/mcp/asset/e980108e-c5a2-4a31-9601-df1a61ede539.png";
const imgImage = "https://www.figma.com/api/mcp/asset/cb9eb09e-5c1d-424a-b81c-383a39a1320b.png";
const imgImage1 = "https://www.figma.com/api/mcp/asset/9a1a3518-fbdb-4fe5-86ec-ec18d7927aa1.png";
const imgImage2 = "https://www.figma.com/api/mcp/asset/f58157ed-7ae6-4a4c-966a-1f3cb42b73e3.png";
const imgIconSupport = "https://www.figma.com/api/mcp/asset/4933af0b-8bce-4570-87d4-3a5bdfd5d2a2.svg";
const imgEllipse = "https://www.figma.com/api/mcp/asset/b69202cc-ba2b-41fe-82bd-3694333eb18c.svg";
const imgIconCheck = "https://www.figma.com/api/mcp/asset/3f3f27d5-720b-4292-8ea6-299db2ac314f.svg";
const imgIconArrowLeft = "https://www.figma.com/api/mcp/asset/adcfcbe0-27b5-4518-8a01-428537d19b71.svg";
const imgIconPin = "https://www.figma.com/api/mcp/asset/893cc7bd-4154-4bdc-b86d-3cf1d6c52881.svg";
const imgIconPlaneSmall = "https://www.figma.com/api/mcp/asset/c20a35fb-8ace-49ed-8c07-82b6f3342f0b.svg";
const imgIconPerson1 = "https://www.figma.com/api/mcp/asset/9b2d8741-7021-4ab9-ac79-5827636b7f38.svg";
const imgIconCalendar = "https://www.figma.com/api/mcp/asset/45742692-3466-4409-b91d-b8679b25b452.svg";
const imgIconArrowLeft1 = "https://www.figma.com/api/mcp/asset/4e6c67dd-4314-4c55-b361-d61aab540027.svg";
const imgCoralDot = "https://www.figma.com/api/mcp/asset/e6c63563-2a77-4a1d-8bce-2ca193d86df3.svg";
const imgLaptopScreen = "https://www.figma.com/api/mcp/asset/fd5859c5-5342-4152-8ece-e135d34f8b09.svg";
const imgTablet = "https://www.figma.com/api/mcp/asset/44fd3289-f109-44b9-aee1-8d13db900182.svg";
const imgIconChart = "https://www.figma.com/api/mcp/asset/bc83460f-2e53-4710-a590-3472d27a3ce7.svg";
const imgIconCheck1 = "https://www.figma.com/api/mcp/asset/3909f6b0-5f2e-4b24-854a-691c49759dba.svg";
const imgIconStaff = "https://www.figma.com/api/mcp/asset/720cd49b-89db-4169-b8a2-75c358351586.svg";

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

function ComponentButton({ className, type = "Auth" }: ComponentButtonProps) {
  const isAuth = type === "Auth";
  const isCompare = type === "Compare";
  const isOrgSolutions = type === "OrgSolutions";
  const isSearchCta = type === "SearchCTA";
  return (
    <div className={className || `content-stretch flex items-center overflow-clip relative ${isOrgSolutions ? "bg-[#28132b] gap-[8px] px-[22px] py-[14px] rounded-[100px]" : isCompare ? "bg-[#ef5b3d] gap-[8px] px-[22px] py-[14px] rounded-[100px]" : isSearchCta ? "bg-[#ef5b3d] justify-center py-[16px] rounded-[16px] w-[572px]" : "bg-[#ef5b3d] gap-[8px] px-[20px] py-[12px] rounded-[100px]"}`} id={isOrgSolutions ? "node-71_153" : isCompare ? "node-71_152" : isSearchCta ? "node-71_150" : "node-71_149"}>
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
        <p className={`[word-break:break-word] leading-[normal] relative shrink-0 text-white whitespace-nowrap ${isSearchCta ? 'font-["Vazirmatn:Bold"] font-bold text-[16px]' : 'font-["Vazirmatn:SemiBold"] font-semibold text-[15px]'}`} dir="auto" id={isSearchCta ? "node-48_35" : "node-45_6"}>
          {isSearchCta ? "پیدا کن" : "ورود / ثبت‌نام"}
        </p>
      )}
      {isCompare && (
        <>
          <div className="relative shrink-0 size-[18px]" data-node-id="67:77" data-name="Icon / Compare">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconCompare} />
          </div>
          <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[15px] text-white whitespace-nowrap" dir="auto" data-node-id="53:47">
            مقایسه کن
          </p>
        </>
      )}
      {isOrgSolutions && (
        <>
          <div className="relative shrink-0 size-[16px]" data-node-id="67:80" data-name="Icon / ChevronLeft">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconChevronLeft} />
          </div>
          <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[15px] text-white whitespace-nowrap" dir="auto" data-node-id="54:73">
            راهکارهای سازمانی
          </p>
        </>
      )}
    </div>
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
        <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[16px] text-white" dir="auto" id={isZandiyeh ? "node-53_61" : "node-53_53"}>
          {isZandiyeh ? "هتل زندیه شیراز" : "هتل عباسی اصفهان"}
        </p>
        <div className="content-stretch flex gap-[6px] items-center overflow-clip relative shrink-0 text-[13px]" id={isZandiyeh ? "node-53_62" : "node-53_54"} data-name="Frame">
          <p className="font-['Vazirmatn:Bold'] font-bold relative shrink-0 text-[#ef5b3d]" id={isZandiyeh ? "node-53_63" : "node-53_55"}>
            {isZandiyeh ? "★ ۴.۵" : "★ ۴.۷"}
          </p>
          <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#f2e5eb]" dir="auto" id={isZandiyeh ? "node-53_64" : "node-53_56"}>
            {isZandiyeh ? "۴ ستاره" : "۵ ستاره"}
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
    <div className={className || `h-[23px] relative ${["Hotel", "Train", "Flight"].includes(item) ? "w-[27px]" : isTour ? "w-[17px]" : isServices ? "w-[73px]" : isMagazine ? "w-[61px]" : "w-[49px]"}`} id={isFlight ? "node-71_93" : isTrain ? "node-71_92" : isHotel ? "node-71_91" : isTour ? "node-71_90" : isServices ? "node-71_89" : isMagazine ? "node-71_88" : "node-71_87"}>
      <p className="[word-break:break-word] absolute font-['Vazirmatn:Medium'] font-medium inset-0 leading-[normal] text-[#3a1b3d] text-[15px] whitespace-nowrap" dir="auto" id={isFlight ? "node-45_14" : isTrain ? "node-45_13" : isHotel ? "node-45_12" : isTour ? "node-45_11" : isServices ? "node-45_10" : isMagazine ? "node-45_9" : "node-45_8"}>
        {isFlight ? "پرواز" : isTrain ? "قطار" : isHotel ? "هتل" : isTour ? "تور" : isServices ? "خدمات سفر" : isMagazine ? "مجله سفر" : "درباره ما"}
      </p>
    </div>
  );
}

export default function KarenSeirHomepageDesktop1440() {
  return (
    <div className="bg-[#fbf3e7] content-stretch flex flex-col items-start relative size-full" data-node-id="44:3" data-name="KarenSeir Homepage / Desktop 1440">
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
            <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[#3a1b3d] text-[19px] whitespace-nowrap" dir="auto" data-node-id="45:17">
              کارن سیر
            </p>
          </div>
        </div>
        <div className="content-stretch flex gap-[56px] items-start overflow-clip relative shrink-0 w-full" data-node-id="46:2" data-name="Hero Row">
          <div className="h-[560px] overflow-clip relative rounded-[32px] shrink-0 w-[600px]" data-node-id="46:3" data-name="Hero Image / Yazd">
            <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[32px] size-full" src={imgHeroImageYazd} />
            <div className="absolute bg-gradient-to-b from-[rgba(26,13,20,0.35)] h-[560px] left-0 to-[rgba(26,13,20,0)] top-0 w-[600px]" data-node-id="46:4" data-name="Scrim" />
          </div>
          <div className="content-stretch flex flex-[1_0_0] flex-col gap-[24px] items-end min-w-px overflow-clip relative" data-node-id="46:5" data-name="Hero Text">
            <div className="[word-break:break-word] font-['Vazirmatn:Black'] font-black leading-[0] min-w-full relative shrink-0 text-[#2a1530] text-[64px] text-right w-[min-content]" data-node-id="46:6">
              <p className="leading-[1.18] mb-0" dir="auto">
                سفر را
              </p>
              <p className="leading-[1.18]" dir="auto">
                زندگی کن
              </p>
            </div>
            <div className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[0] relative shrink-0 text-[#6e5e70] text-[17px] text-right w-[420px]" data-node-id="46:7">
              <p className="leading-[1.6] mb-0" dir="auto">
                از اولین جست‌وجو تا آخرین خاطره،
              </p>
              <p className="leading-[1.6]" dir="auto">
                همه‌چیز در کارن سیر کنار هم است.
              </p>
            </div>
            <div className="content-stretch flex gap-[32px] items-center overflow-clip relative shrink-0" data-node-id="46:8" data-name="Trust Badges">
              <div className="content-stretch flex gap-[10px] items-center overflow-clip relative shrink-0" data-node-id="46:9" data-name="Frame">
                <div className="relative shrink-0 size-[18px]" data-node-id="68:58" data-name="Icon / Support">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconSupport} />
                </div>
                <div className="relative shrink-0 size-[40px]" data-node-id="46:10" data-name="Ellipse">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgEllipse} />
                </div>
                <div className="[word-break:break-word] content-stretch flex flex-col gap-[2px] items-end leading-[normal] overflow-clip relative shrink-0 whitespace-nowrap" data-node-id="46:11" data-name="Frame">
                  <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[#2a1530] text-[14px]" dir="auto" data-node-id="46:12">
                    پشتیبانی
                  </p>
                  <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#6e5e70] text-[12px]" dir="auto" data-node-id="46:13">
                    ۲۴ ساعته
                  </p>
                </div>
              </div>
              <div className="content-stretch flex gap-[10px] items-center overflow-clip relative shrink-0" data-node-id="46:14" data-name="Frame">
                <div className="relative shrink-0 size-[18px]" data-node-id="68:62" data-name="Icon / Check">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconCheck} />
                </div>
                <div className="relative shrink-0 size-[40px]" data-node-id="46:15" data-name="Ellipse">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgEllipse} />
                </div>
                <div className="[word-break:break-word] content-stretch flex flex-col gap-[2px] items-end leading-[normal] overflow-clip relative shrink-0 whitespace-nowrap" data-node-id="46:16" data-name="Frame">
                  <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[#2a1530] text-[14px]" dir="auto" data-node-id="46:17">
                    رزرو
                  </p>
                  <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#6e5e70] text-[12px]" dir="auto" data-node-id="46:18">
                    قابل پیگیری
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="absolute bg-white content-stretch flex gap-[10px] items-center left-[44px] overflow-clip pl-[14px] pr-[8px] py-[8px] rounded-[16px] shadow-[0px_6px_16px_0px_rgba(77,51,38,0.15)] top-[171px]" data-node-id="48:2" data-name="Mini Card / Shiraz">
          <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:3">
            شیراز
          </p>
          <div className="relative rounded-[12px] shrink-0 size-[48px]" data-node-id="48:4" data-name="thumb">
            <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[12px] size-full" src={imgThumb2} />
          </div>
          <div className="relative shrink-0 size-[14px]" data-node-id="72:118" data-name="Icon / ArrowLeft">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconArrowLeft} />
          </div>
        </div>
        <div className="absolute bg-white content-stretch flex gap-[10px] items-center left-[44px] overflow-clip pl-[14px] pr-[8px] py-[8px] rounded-[16px] shadow-[0px_6px_16px_0px_rgba(77,51,38,0.15)] top-[241px]" data-node-id="48:6" data-name="Mini Card / Kish">
          <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:7">
            کیش
          </p>
          <div className="relative rounded-[12px] shrink-0 size-[48px]" data-node-id="48:8" data-name="thumb">
            <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[12px] size-full" src={imgThumb3} />
          </div>
          <div className="relative shrink-0 size-[14px]" data-node-id="72:120" data-name="Icon / ArrowLeft">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconArrowLeft} />
          </div>
        </div>
        <div className="absolute bg-white content-stretch flex flex-col gap-[16px] items-end left-[410px] overflow-clip p-[24px] rounded-[28px] shadow-[0px_20px_40px_-8px_rgba(77,38,51,0.18)] top-[520px] w-[620px]" data-node-id="48:10" data-name="Search Card">
          <div className="bg-white content-stretch flex gap-[4px] items-center overflow-clip relative shrink-0" data-node-id="48:11" data-name="Frame">
            <div className="bg-[rgba(0,0,0,0)] content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[14px] shrink-0" data-node-id="48:12" data-name="Frame">
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:13">
                تور + هتل
              </p>
            </div>
            <div className="bg-[rgba(0,0,0,0)] content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[14px] shrink-0" data-node-id="48:14" data-name="Frame">
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:15">
                تشریفات فرودگاه
              </p>
            </div>
            <div className="bg-[rgba(0,0,0,0)] content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[14px] shrink-0" data-node-id="48:16" data-name="Frame">
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:17">
                هتل
              </p>
            </div>
            <div className="bg-[#2a1530] content-stretch flex items-start overflow-clip px-[18px] py-[10px] relative rounded-[14px] shrink-0" data-node-id="48:18" data-name="Frame">
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[14px] text-white whitespace-nowrap" dir="auto" data-node-id="48:19">
                پرواز
              </p>
            </div>
          </div>
          <div className="bg-white content-stretch flex gap-[12px] items-start overflow-clip relative shrink-0 w-full" data-node-id="48:20" data-name="Frame">
            <div className="bg-[#f6eee2] content-stretch flex flex-[1_0_0] gap-[8px] items-center min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[16px]" data-node-id="48:21" data-name="Frame">
              <div className="relative shrink-0 size-[16px]" data-node-id="68:64" data-name="Icon / Pin">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconPin} />
              </div>
              <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:23">
                به کجا؟
              </p>
            </div>
            <div className="bg-[#f6eee2] content-stretch flex flex-[1_0_0] gap-[8px] items-center min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[16px]" data-node-id="48:24" data-name="Frame">
              <div className="relative shrink-0 size-[16px]" data-node-id="68:67" data-name="Icon / PlaneSmall">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconPlaneSmall} />
              </div>
              <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:26">
                از کجا؟
              </p>
            </div>
          </div>
          <div className="bg-white content-stretch flex gap-[12px] items-start overflow-clip relative shrink-0 w-full" data-node-id="48:27" data-name="Frame">
            <div className="bg-[#f6eee2] content-stretch flex flex-[1_0_0] gap-[8px] items-center min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[16px]" data-node-id="48:28" data-name="Frame">
              <div className="relative shrink-0 size-[16px]" data-node-id="68:69" data-name="Icon / Person">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconPerson1} />
              </div>
              <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:30">
                مسافران
              </p>
            </div>
            <div className="bg-[#f6eee2] content-stretch flex flex-[1_0_0] gap-[8px] items-center min-w-px overflow-clip px-[16px] py-[14px] relative rounded-[16px]" data-node-id="48:31" data-name="Frame">
              <div className="relative shrink-0 size-[16px]" data-node-id="68:72" data-name="Icon / Calendar">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconCalendar} />
              </div>
              <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#2a1530] text-[14px] whitespace-nowrap" dir="auto" data-node-id="48:33">
                تاریخ سفر
              </p>
            </div>
          </div>
          <ComponentButton className="bg-[#ef5b3d] content-stretch flex items-center justify-center overflow-clip py-[16px] relative rounded-[16px] shrink-0 w-[572px]" type="SearchCTA" />
          <p className="[word-break:break-word] font-['Vazirmatn:Medium'] font-medium leading-[normal] min-w-full relative shrink-0 text-[#ef5b3d] text-[13px] text-center w-[min-content]" dir="auto" data-node-id="48:36">
            ✦ با دستیار هوشمند برنامه‌ریزی کن
          </p>
        </div>
        <div className="h-[144px] relative shrink-0 w-full" data-node-id="49:2" data-name="Spacer / Search Card Overlap" />
      </div>
      <div className="bg-white content-stretch flex flex-col gap-[32px] items-end overflow-clip px-[64px] py-[40px] relative shrink-0 w-full" data-node-id="50:2" data-name="Section / Bento Destinations">
        <div className="[word-break:break-word] font-['Vazirmatn:Black'] font-black leading-[0] relative shrink-0 text-[#2a1530] text-[34px] text-right whitespace-nowrap" data-node-id="50:3">
          <p className="leading-[1.3] mb-0" dir="auto">
            کجای ایران
          </p>
          <p className="leading-[1.3]" dir="auto">
            صدایت می‌زند؟
          </p>
        </div>
        <div className="content-stretch flex gap-[20px] items-start overflow-clip relative shrink-0 w-full" data-node-id="50:7" data-name="Bento Row">
          <div className="h-[420px] overflow-clip relative rounded-[28px] shrink-0 w-[404px]" data-node-id="50:8" data-name="Tile / Qeshm">
            <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[28px] size-full" src={imgTileQeshm} />
            <div className="absolute bg-gradient-to-b from-[rgba(0,0,0,0.55)] inset-0 to-[55%] to-[rgba(0,0,0,0)]" data-node-id="I50:8;50:5" data-name="Scrim" />
            <p className="[word-break:break-word] absolute bottom-[65px] font-['Vazirmatn:Bold'] font-bold leading-[normal] left-[24px] text-[26px] text-white translate-y-full whitespace-nowrap" dir="auto" data-node-id="I50:8;50:6">
              قشم
            </p>
          </div>
          <div className="h-[420px] overflow-clip relative rounded-[28px] shrink-0 w-[404px]" data-node-id="50:11" data-name="Tile / Shiraz">
            <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[28px] size-full" src={imgTileShiraz} />
            <div className="absolute bg-gradient-to-b from-[rgba(0,0,0,0.55)] inset-0 to-[55%] to-[rgba(0,0,0,0)]" data-node-id="I50:11;50:5" data-name="Scrim" />
            <p className="[word-break:break-word] absolute bottom-[65px] font-['Vazirmatn:Bold'] font-bold leading-[normal] left-[24px] text-[26px] text-white translate-y-full whitespace-nowrap" dir="auto" data-node-id="I50:11;50:6">
              شیراز
            </p>
          </div>
          <div className="content-stretch flex flex-[1_0_0] flex-col gap-[20px] items-start min-w-px overflow-clip relative" data-node-id="50:14" data-name="Bento Right Col">
            <div className="h-[200px] overflow-clip relative rounded-[28px] shrink-0 w-full" data-node-id="50:15" data-name="Tile / Masuleh">
              <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[28px] size-full" src={imgTileMasuleh} />
              <div className="absolute bg-gradient-to-b from-[rgba(0,0,0,0.55)] inset-0 to-[55%] to-[rgba(0,0,0,0)]" data-node-id="I50:15;50:5" data-name="Scrim" />
              <p className="[word-break:break-word] absolute bottom-[65px] font-['Vazirmatn:Bold'] font-bold leading-[normal] left-[24px] text-[26px] text-white translate-y-full whitespace-nowrap" dir="auto" data-node-id="I50:15;50:6">
                ماسوله
              </p>
            </div>
            <div className="h-[200px] overflow-clip relative rounded-[28px] shrink-0 w-full" data-node-id="50:18" data-name="Tile / Isfahan">
              <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-[28px] size-full" src={imgTileIsfahan} />
              <div className="absolute bg-gradient-to-b from-[rgba(0,0,0,0.55)] inset-0 to-[55%] to-[rgba(0,0,0,0)]" data-node-id="I50:18;50:5" data-name="Scrim" />
              <p className="[word-break:break-word] absolute bottom-[65px] font-['Vazirmatn:Bold'] font-bold leading-[normal] left-[24px] text-[26px] text-white translate-y-full whitespace-nowrap" dir="auto" data-node-id="I50:18;50:6">
                اصفهان
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="bg-white content-stretch flex flex-col gap-[28px] items-end overflow-clip pb-[40px] pt-[8px] px-[64px] relative shrink-0 w-full" data-node-id="51:10" data-name="Section / Curated Trips">
        <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[#2a1530] text-[28px] text-right whitespace-nowrap" dir="auto" data-node-id="51:11">
          سفرهای انتخاب‌شده برای تو
        </p>
        <div className="content-stretch flex gap-[24px] items-start overflow-clip relative shrink-0 w-full" data-node-id="51:24" data-name="Trips Row">
          <div className="bg-[#fffcf9] content-stretch drop-shadow-[0px_8px_12px_rgba(77,51,51,0.08)] flex flex-[1_0_0] flex-col items-start min-w-px relative rounded-[24px]" data-node-id="51:25" data-name="Trip / Shiraz">
            <div className="h-[220px] relative rounded-tl-[24px] rounded-tr-[24px] shrink-0 w-full" data-node-id="I51:25;51:13" data-name="Image">
              <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-tl-[24px] rounded-tr-[24px] size-full" src={imgImage} />
            </div>
            <div className="bg-white content-stretch flex flex-col gap-[10px] items-end overflow-clip p-[20px] relative shrink-0 w-full" data-node-id="I51:25;51:14" data-name="Body">
              <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[#2a1530] text-[19px] text-right w-full" dir="auto" data-node-id="I51:25;51:15">
                سه روز در شیراز
              </p>
              <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#807080] text-[14px] text-right w-full" dir="auto" data-node-id="I51:25;51:16">
                ۳ روز و ۲ شب
              </p>
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[15px] text-right w-full" dir="auto" data-node-id="I51:25;51:17">
                شروع از ۶,۹۰۰,۰۰۰ تومان
              </p>
              <div className="bg-white content-stretch flex items-center justify-between overflow-clip pt-[6px] relative shrink-0 w-full" data-node-id="I51:25;51:18" data-name="Bottom Row">
                <div className="bg-[#ef5b3d] overflow-clip relative rounded-[20px] shrink-0 size-[40px]" data-node-id="I51:25;51:19" data-name="Arrow Button">
                  <div className="absolute left-[8px] size-[16px] top-[14.5px]" data-node-id="I51:25;72:116" data-name="Icon / ArrowLeft">
                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconArrowLeft1} />
                  </div>
                </div>
                <div className="[word-break:break-word] bg-white content-stretch flex gap-[4px] items-center leading-[normal] overflow-clip relative shrink-0 text-[14px] whitespace-nowrap" data-node-id="I51:25;51:21" data-name="Rating">
                  <p className="font-['Vazirmatn:Bold'] font-bold relative shrink-0 text-[#ef5b3d]" data-node-id="I51:25;51:22">
                    ★
                  </p>
                  <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[#2a1530]" data-node-id="I51:25;51:23">
                    ۴.۷
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-[#fffcf9] content-stretch drop-shadow-[0px_8px_12px_rgba(77,51,51,0.08)] flex flex-[1_0_0] flex-col items-start min-w-px relative rounded-[24px]" data-node-id="51:37" data-name="Trip / Qeshm">
            <div className="h-[220px] relative rounded-tl-[24px] rounded-tr-[24px] shrink-0 w-full" data-node-id="I51:37;51:13" data-name="Image">
              <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-tl-[24px] rounded-tr-[24px] size-full" src={imgImage1} />
            </div>
            <div className="bg-white content-stretch flex flex-col gap-[10px] items-end overflow-clip p-[20px] relative shrink-0 w-full" data-node-id="I51:37;51:14" data-name="Body">
              <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[#2a1530] text-[19px] text-right w-full" dir="auto" data-node-id="I51:37;51:15">
                آرامش در جزیره قشم
              </p>
              <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#807080] text-[14px] text-right w-full" dir="auto" data-node-id="I51:37;51:16">
                ۴ روز و ۳ شب
              </p>
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[15px] text-right w-full" dir="auto" data-node-id="I51:37;51:17">
                شروع از ۷,۴۵۰,۰۰۰ تومان
              </p>
              <div className="bg-white content-stretch flex items-center justify-between overflow-clip pt-[6px] relative shrink-0 w-full" data-node-id="I51:37;51:18" data-name="Bottom Row">
                <div className="bg-[#ef5b3d] overflow-clip relative rounded-[20px] shrink-0 size-[40px]" data-node-id="I51:37;51:19" data-name="Arrow Button">
                  <div className="absolute left-[8px] size-[16px] top-[14.5px]" data-node-id="I51:37;72:116" data-name="Icon / ArrowLeft">
                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconArrowLeft1} />
                  </div>
                </div>
                <div className="[word-break:break-word] bg-white content-stretch flex gap-[4px] items-center leading-[normal] overflow-clip relative shrink-0 text-[14px] whitespace-nowrap" data-node-id="I51:37;51:21" data-name="Rating">
                  <p className="font-['Vazirmatn:Bold'] font-bold relative shrink-0 text-[#ef5b3d]" data-node-id="I51:37;51:22">
                    ★
                  </p>
                  <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[#2a1530]" data-node-id="I51:37;51:23">
                    ۴.۹
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-[#fffcf9] content-stretch drop-shadow-[0px_8px_12px_rgba(77,51,51,0.08)] flex flex-[1_0_0] flex-col items-start min-w-px relative rounded-[24px]" data-node-id="51:49" data-name="Trip / North">
            <div className="h-[220px] relative rounded-tl-[24px] rounded-tr-[24px] shrink-0 w-full" data-node-id="I51:49;51:13" data-name="Image">
              <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none rounded-tl-[24px] rounded-tr-[24px] size-full" src={imgImage2} />
            </div>
            <div className="bg-white content-stretch flex flex-col gap-[10px] items-end overflow-clip p-[20px] relative shrink-0 w-full" data-node-id="I51:49;51:14" data-name="Body">
              <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[#2a1530] text-[19px] text-right w-full" dir="auto" data-node-id="I51:49;51:15">
                مسیر سبز شمال
              </p>
              <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#807080] text-[14px] text-right w-full" dir="auto" data-node-id="I51:49;51:16">
                ۳ روز و ۲ شب
              </p>
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[15px] text-right w-full" dir="auto" data-node-id="I51:49;51:17">
                شروع از ۵,۲۵۰,۰۰۰ تومان
              </p>
              <div className="bg-white content-stretch flex items-center justify-between overflow-clip pt-[6px] relative shrink-0 w-full" data-node-id="I51:49;51:18" data-name="Bottom Row">
                <div className="bg-[#ef5b3d] overflow-clip relative rounded-[20px] shrink-0 size-[40px]" data-node-id="I51:49;51:19" data-name="Arrow Button">
                  <div className="absolute left-[8px] size-[16px] top-[14.5px]" data-node-id="I51:49;72:116" data-name="Icon / ArrowLeft">
                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconArrowLeft1} />
                  </div>
                </div>
                <div className="[word-break:break-word] bg-white content-stretch flex gap-[4px] items-center leading-[normal] overflow-clip relative shrink-0 text-[14px] whitespace-nowrap" data-node-id="I51:49;51:21" data-name="Rating">
                  <p className="font-['Vazirmatn:Bold'] font-bold relative shrink-0 text-[#ef5b3d]" data-node-id="I51:49;51:22">
                    ★
                  </p>
                  <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[#2a1530]" data-node-id="I51:49;51:23">
                    ۴.۵
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="bg-[#fbf4e6] content-stretch flex flex-col items-start overflow-clip px-[64px] py-[32px] relative shrink-0 w-full" data-node-id="52:43" data-name="AI Travel Assistant / Desktop 1440">
        <div className="bg-[#fbf4e6] border border-[#e0ccbf] border-solid content-stretch flex gap-[32px] h-[360px] items-start p-[40px] relative rounded-[32px] shrink-0 w-full" data-node-id="94:236" data-name="AI Travel Assistant">
          <div className="bg-[#220e2e] content-stretch flex flex-col gap-[18px] h-[280px] items-start p-[28px] relative rounded-[28px] shrink-0 w-[300px]" data-node-id="94:237" data-name="AI Identity">
            <div className="bg-[#ed4f40] content-stretch flex items-start px-[16px] py-[8px] relative rounded-[999px] shrink-0" data-node-id="94:238" data-name="AI Badge">
              <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[1.65] relative shrink-0 text-[18px] text-right text-white w-[18px]" data-node-id="94:239">
                AI
              </p>
            </div>
            <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-none relative shrink-0 text-[72px] text-right text-white w-[244px]" data-node-id="94:240">
              AI
            </p>
            <div className="[word-break:break-word] font-['Vazirmatn:Medium'] font-medium leading-[0] opacity-82 relative shrink-0 text-[15px] text-right text-white w-[244px]" data-node-id="94:241">
              <p className="leading-[1.65] mb-0" dir="auto">
                هوشمندی برای تصمیم بهتر؛
              </p>
              <p className="leading-[1.65]" dir="auto">
                نه جایگزین انتخاب شما
              </p>
            </div>
          </div>
          <div className="bg-[#fbf4e6] content-stretch flex flex-[1_0_0] flex-col gap-[18px] h-full items-start min-w-px py-[4px] relative" data-node-id="94:242" data-name="Assistant Content">
            <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[1.65] relative shrink-0 text-[#ed4f40] text-[14px] text-right w-[900px]" dir="auto" data-node-id="94:243">
              دستیار هوشمند سفر
            </p>
            <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[1.35] relative shrink-0 text-[#220e2e] text-[32px] text-right w-[900px]" dir="auto" data-node-id="94:244">
              دستیار هوشمند سفر کارن‌سیر
            </p>
            <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[1.65] relative shrink-0 text-[#291b29] text-[18px] text-right w-[900px]" dir="auto" data-node-id="94:245">
              مقصد، بودجه و شرایطت را بگو؛ سفرت را هوشمندانه طراحی و مقایسه می‌کنم.
            </p>
            <div className="bg-[#fbf4e6] content-start flex flex-wrap gap-[10px] items-start justify-end relative shrink-0 w-full" data-node-id="94:246" data-name="Capabilities">
              <div className="bg-white border border-[#e0ccbf] border-solid content-stretch flex gap-[8px] items-start px-[14px] py-[9px] relative rounded-[999px] shrink-0" data-node-id="94:259" data-name="Capability">
                <div className="relative shrink-0 size-[7px]" data-node-id="94:260" data-name="Coral Dot">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgCoralDot} />
                </div>
                <p className="[word-break:break-word] font-['Vazirmatn:Medium'] font-medium leading-[1.65] relative shrink-0 text-[#291b29] text-[14px] text-right w-[180px]" dir="auto" data-node-id="94:261">
                  راهنمایی قبل، حین و بعد از سفر
                </p>
              </div>
              <div className="bg-white border border-[#e0ccbf] border-solid content-stretch flex gap-[8px] items-start px-[14px] py-[9px] relative rounded-[999px] shrink-0" data-node-id="94:256" data-name="Capability">
                <div className="relative shrink-0 size-[7px]" data-node-id="94:257" data-name="Coral Dot">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgCoralDot} />
                </div>
                <p className="[word-break:break-word] font-['Vazirmatn:Medium'] font-medium leading-[1.65] relative shrink-0 text-[#291b29] text-[14px] text-right w-[144px]" dir="auto" data-node-id="94:258">
                  پیشنهاد گزینه‌های مناسب
                </p>
              </div>
              <div className="bg-white border border-[#e0ccbf] border-solid content-stretch flex gap-[8px] items-start px-[14px] py-[9px] relative rounded-[999px] shrink-0" data-node-id="94:253" data-name="Capability">
                <div className="relative shrink-0 size-[7px]" data-node-id="94:254" data-name="Coral Dot">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgCoralDot} />
                </div>
                <p className="[word-break:break-word] font-['Vazirmatn:Medium'] font-medium leading-[1.65] relative shrink-0 text-[#291b29] text-[14px] text-right w-[259px]" dir="auto" data-node-id="94:255">
                  مقایسه پرواز، هتل، پرواز + هتل و سایر خدمات
                </p>
              </div>
              <div className="bg-white border border-[#e0ccbf] border-solid content-stretch flex gap-[8px] items-start px-[14px] py-[9px] relative rounded-[999px] shrink-0" data-node-id="94:250" data-name="Capability">
                <div className="relative shrink-0 size-[7px]" data-node-id="94:251" data-name="Coral Dot">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgCoralDot} />
                </div>
                <p className="[word-break:break-word] font-['Vazirmatn:Medium'] font-medium leading-[1.65] relative shrink-0 text-[#291b29] text-[14px] text-right w-[85px]" dir="auto" data-node-id="94:252">
                  برنامه‌ریزی سفر
                </p>
              </div>
              <div className="bg-white border border-[#e0ccbf] border-solid content-stretch flex gap-[8px] items-start px-[14px] py-[9px] relative rounded-[999px] shrink-0" data-node-id="94:247" data-name="Capability">
                <div className="relative shrink-0 size-[7px]" data-node-id="94:248" data-name="Coral Dot">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgCoralDot} />
                </div>
                <p className="[word-break:break-word] font-['Vazirmatn:Medium'] font-medium leading-[1.65] relative shrink-0 text-[#291b29] text-[14px] text-right w-[181px]" dir="auto" data-node-id="94:249">
                  پیشنهاد مقصد متناسب با بودجه
                </p>
              </div>
            </div>
            <div className="bg-[#ed4f40] content-stretch flex items-start px-[22px] py-[13px] relative rounded-[999px] shrink-0" data-node-id="94:262" data-name="Primary CTA">
              <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[1.65] relative shrink-0 text-[16px] text-right text-white w-[111px]" dir="auto" data-node-id="94:263">
                شروع گفتگو با AI
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="bg-[#28132b] content-stretch flex flex-col gap-[32px] items-start overflow-clip px-[64px] py-[44px] relative shrink-0 w-full" data-node-id="53:43" data-name="Section / Hotel Comparison">
        <div className="content-stretch flex items-center justify-between overflow-clip relative shrink-0 w-full" data-node-id="53:44" data-name="Top Row">
          <ComponentButton className="bg-[#ef5b3d] content-stretch flex gap-[8px] items-center overflow-clip px-[22px] py-[14px] relative rounded-[100px] shrink-0" type="Compare" />
          <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[22px] text-white whitespace-nowrap" dir="auto" data-node-id="53:48">
            دو انتخاب داری؟ کنار هم ببین
          </p>
        </div>
        <div className="content-stretch flex items-center justify-between overflow-clip relative shrink-0 w-full" data-node-id="53:49" data-name="Hotels Row">
          <ComponentHotelRow className="content-stretch flex gap-[16px] items-center overflow-clip relative shrink-0" />
          <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[#f2e5eb] text-[14px] whitespace-nowrap" dir="auto" data-node-id="53:57">
            یا
          </p>
          <ComponentHotelRow className="content-stretch flex gap-[16px] items-center overflow-clip relative shrink-0" hotel="Zandiyeh" />
        </div>
      </div>
      <div className="bg-[#efdbbf] content-stretch flex gap-[64px] items-center overflow-clip px-[64px] py-[56px] relative shrink-0 w-full" data-node-id="54:43" data-name="Section / Organizational Travel">
        <div className="h-[340px] overflow-clip relative shrink-0 w-[480px]" data-node-id="54:44" data-name="Dashboard Illustration">
          <div className="absolute h-[240px] left-[60px] top-[30px] w-[360px]" data-node-id="54:45" data-name="Laptop Screen">
            <div className="absolute inset-[-8.33%_-11.11%_-25%_-11.11%]">
              <img alt="" className="block max-w-none size-full" src={imgLaptopScreen} />
            </div>
          </div>
          <div className="absolute h-[160px] left-0 top-[140px] w-[120px]" data-node-id="54:53" data-name="Tablet">
            <div className="absolute inset-[-10%_-26.67%_-30%_-26.67%]">
              <img alt="" className="block max-w-none size-full" src={imgTablet} />
            </div>
          </div>
          <div className="absolute bg-[#668c59] h-[60px] left-[400px] rounded-[8px] top-[260px] w-[50px]" data-node-id="54:55" data-name="Plant" />
        </div>
        <div className="content-stretch flex flex-[1_0_0] flex-col gap-[28px] items-end min-w-px overflow-clip relative" data-node-id="54:56" data-name="Org Text">
          <p className="[word-break:break-word] font-['Vazirmatn:Black'] font-black leading-[normal] relative shrink-0 text-[#2a1530] text-[30px] text-right w-[400px]" dir="auto" data-node-id="54:57">
            سفر سازمانی، بدون پیچیدگی
          </p>
          <div className="content-stretch flex gap-[36px] items-start overflow-clip relative shrink-0" data-node-id="54:58" data-name="Frame">
            <div className="content-stretch flex flex-col gap-[10px] items-center overflow-clip relative shrink-0" data-node-id="54:59" data-name="Frame">
              <div className="bg-white overflow-clip relative rounded-[16px] shrink-0 size-[52px]" data-node-id="54:60" data-name="Frame">
                <div className="absolute left-[14px] size-[20px] top-[12px]" data-node-id="67:64" data-name="Icon / Chart">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconChart} />
                </div>
              </div>
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[13px] text-center whitespace-nowrap" dir="auto" data-node-id="54:62">
                گزارش مالی
              </p>
            </div>
            <div className="content-stretch flex flex-col gap-[10px] items-center overflow-clip relative shrink-0" data-node-id="54:63" data-name="Frame">
              <div className="bg-white overflow-clip relative rounded-[16px] shrink-0 size-[52px]" data-node-id="54:64" data-name="Frame">
                <div className="absolute left-[14px] size-[20px] top-[12px]" data-node-id="67:69" data-name="Icon / Check">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconCheck1} />
                </div>
              </div>
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[13px] text-center whitespace-nowrap" dir="auto" data-node-id="54:66">
                تأیید مرحله‌ای
              </p>
            </div>
            <div className="content-stretch flex flex-col gap-[10px] items-center overflow-clip relative shrink-0" data-node-id="54:67" data-name="Frame">
              <div className="bg-white overflow-clip relative rounded-[16px] shrink-0 size-[52px]" data-node-id="54:68" data-name="Frame">
                <div className="absolute left-[14px] size-[20px] top-[12px]" data-node-id="67:71" data-name="Icon / Staff">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIconStaff} />
                </div>
              </div>
              <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[#2a1530] text-[13px] text-center whitespace-nowrap" dir="auto" data-node-id="54:70">
                اعتبار کارکنان
              </p>
            </div>
          </div>
          <ComponentButton className="bg-[#28132b] content-stretch flex gap-[8px] items-center overflow-clip px-[22px] py-[14px] relative rounded-[100px] shrink-0" type="OrgSolutions" />
        </div>
      </div>
      <div className="bg-[#210f24] h-[114px] relative rounded-tl-[56px] rounded-tr-[56px] shrink-0 w-full" data-node-id="56:43" data-name="Section / Reserved Modular Services Strip" />
      <div className="bg-[#210f24] content-stretch flex flex-col gap-[40px] items-start overflow-clip pb-[32px] pt-[48px] px-[64px] relative shrink-0 w-full" data-node-id="57:43" data-name="Section / Footer">
        <div className="content-stretch flex items-start justify-between overflow-clip relative shrink-0 w-full" data-node-id="57:44" data-name="Frame">
          <div className="content-stretch flex flex-col gap-[14px] items-start overflow-clip relative shrink-0" data-node-id="57:45" data-name="Frame">
            <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[14px] text-white whitespace-nowrap" dir="auto" data-node-id="57:46">
              دانلود اپلیکیشن کارن سیر
            </p>
            <div className="content-stretch flex gap-[10px] items-start overflow-clip relative shrink-0" data-node-id="57:47" data-name="Frame">
              <div className="bg-[#38263b] content-stretch flex items-start overflow-clip px-[16px] py-[10px] relative rounded-[10px] shrink-0" data-node-id="57:48" data-name="Frame">
                <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[12px] text-white whitespace-nowrap" data-node-id="57:49">
                  Google Play
                </p>
              </div>
              <div className="bg-[#38263b] content-stretch flex items-start overflow-clip px-[16px] py-[10px] relative rounded-[10px] shrink-0" data-node-id="57:50" data-name="Frame">
                <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[12px] text-white whitespace-nowrap" dir="auto" data-node-id="57:51">
                  بازار
                </p>
              </div>
            </div>
          </div>
          <div className="content-stretch flex flex-col gap-[10px] items-end overflow-clip relative shrink-0" data-node-id="57:52" data-name="Frame">
            <div className="content-stretch flex gap-[8px] items-center overflow-clip relative shrink-0" data-node-id="57:53" data-name="Frame">
              <ComponentLogoMark className="relative shrink-0 size-[30px]" />
              <p className="[word-break:break-word] font-['Vazirmatn:Bold'] font-bold leading-[normal] relative shrink-0 text-[20px] text-white whitespace-nowrap" dir="auto" data-node-id="57:55">
                کارن سیر
              </p>
            </div>
            <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#bfb2bf] text-[13px] text-right whitespace-nowrap" dir="auto" data-node-id="57:56">
              سفر، قصه‌ی ماست. کارن سیر، همراه هر سفر توست.
            </p>
            <p className="[word-break:break-word] font-['Vazirmatn:SemiBold'] font-semibold leading-[normal] relative shrink-0 text-[13px] text-white whitespace-pre" dir="auto" data-node-id="57:57">{`پشتیبانی ۲۴ ساعته  ۰۲۱-۹۲۰۰۰۰۰۰`}</p>
          </div>
        </div>
        <div className="bg-[rgba(255,255,255,0.12)] h-px relative shrink-0 w-full" data-node-id="57:58" data-name="Rectangle" />
        <div className="content-stretch flex gap-[80px] items-start overflow-clip relative shrink-0 w-full" data-node-id="57:59" data-name="Frame">
          <div className="[word-break:break-word] content-stretch flex flex-col gap-[12px] items-end leading-[normal] overflow-clip relative shrink-0 whitespace-nowrap" data-node-id="57:60" data-name="Frame">
            <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[14px] text-white" dir="auto" data-node-id="57:61">
              کارن سیر
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:62">
              درباره ما
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:63">
              تماس با ما
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:64">
              فرصت‌های شغلی
            </p>
          </div>
          <div className="[word-break:break-word] content-stretch flex flex-col gap-[12px] items-end leading-[normal] overflow-clip relative shrink-0 whitespace-nowrap" data-node-id="57:65" data-name="Frame">
            <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[14px] text-white" dir="auto" data-node-id="57:66">
              پشتیبانی
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:67">
              مرکز راهنما
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:68">
              پرسش‌های متداول
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:69">
              شرایط استرداد
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:70">
              گزارش تخلف
            </p>
          </div>
          <div className="[word-break:break-word] content-stretch flex flex-col gap-[12px] items-end leading-[normal] overflow-clip relative shrink-0 whitespace-nowrap" data-node-id="57:71" data-name="Frame">
            <p className="font-['Vazirmatn:SemiBold'] font-semibold relative shrink-0 text-[14px] text-white" dir="auto" data-node-id="57:72">
              قوانین
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:73">
              قوانین و مقررات
            </p>
            <p className="font-['Vazirmatn:Regular'] font-normal relative shrink-0 text-[#bfb2bf] text-[13px]" dir="auto" data-node-id="57:74">
              حریم خصوصی
            </p>
          </div>
          <div className="flex-[1_0_0] h-[10px] min-w-px relative" data-node-id="57:75" data-name="Frame" />
        </div>
        <div className="content-stretch flex items-center justify-between overflow-clip relative shrink-0 w-full" data-node-id="57:76" data-name="Frame">
          <div className="content-stretch flex gap-[12px] items-start overflow-clip relative shrink-0" data-node-id="57:77" data-name="Frame">
            <ComponentSocialIcon className="bg-[rgba(255,255,255,0.1)] overflow-clip relative rounded-[17px] shrink-0 size-[34px]" />
            <ComponentSocialIcon className="bg-[rgba(255,255,255,0.1)] overflow-clip relative rounded-[17px] shrink-0 size-[34px]" platform="Telegram" />
            <ComponentSocialIcon className="bg-[rgba(255,255,255,0.1)] overflow-clip relative rounded-[17px] shrink-0 size-[34px]" platform="LinkedIn" />
          </div>
          <p className="[word-break:break-word] font-['Vazirmatn:Regular'] font-normal leading-[normal] relative shrink-0 text-[#bfb2bf] text-[12px] whitespace-nowrap" dir="auto" data-node-id="57:84">
            © کارن سیر. کلیه حقوق محفوظ است.
          </p>
        </div>
      </div>
    </div>
  );
}