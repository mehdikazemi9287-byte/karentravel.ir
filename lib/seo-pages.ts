/* Title, description and sitemap settings of every fixed public page (one row per URL).
   Title = what people search for; the root template adds « | کارن تراول». Description = 120–160 characters.
   Pages read their metadata with seoFor('/path'); app/sitemap.ts lists every row; tests/seo/seo-check.mjs checks them. */
import type {Metadata, MetadataRoute} from 'next';
import {pageMetadata} from './seo';

type Freq = NonNullable<MetadataRoute.Sitemap[number]['changeFrequency']>;
export type PublicPage = {path: string; title: string; description: string; changeFrequency: Freq; priority: number; absoluteTitle?: boolean};

export const PUBLIC_PAGES: PublicPage[] = [
  {path: '/', absoluteTitle: true, title: 'کارن تراول | خرید بلیط هواپیما، قطار، رزرو هتل و تور', changeFrequency: 'daily', priority: 1,
    description: 'خرید آنلاین بلیط هواپیما و قطار، رزرو هتل، تور داخلی و خارجی و خدمات مقصد در کارن تراول؛ مقایسهٔ شفاف گزینه‌ها و پشتیبانی کارشناسان در تمام مسیر سفر.'},
  {path: '/flights', title: 'خرید بلیط هواپیما داخلی و خارجی', changeFrequency: 'daily', priority: .9,
    description: 'خرید بلیط هواپیما ارزان برای پروازهای داخلی و خارجی در کارن تراول؛ جست‌وجوی پرواز سیستمی و چارتری، مقایسهٔ قیمت و قوانین استرداد و صدور آنلاین بلیط.'},
  {path: '/trains', title: 'خرید بلیط قطار', changeFrequency: 'daily', priority: .8,
    description: 'خرید بلیط قطار مسافربری به مقصد مشهد، شیراز، اصفهان و دیگر شهرها در کارن تراول؛ مشاهدهٔ ساعت حرکت، نوع واگن و ثبت درخواست بلیط با پشتیبانی کارشناسان.'},
  {path: '/hotels', title: 'رزرو هتل و اقامتگاه', changeFrequency: 'daily', priority: .9,
    description: 'رزرو هتل در مشهد، کیش، شیراز، اصفهان و دیگر شهرهای ایران با کارن تراول؛ مقایسهٔ امکانات، موقعیت و قوانین کنسلی هتل‌ها و اقامتگاه‌ها پیش از رزرو.'},
  {path: '/tours', title: 'تور داخلی و خارجی؛ تور کیش، مشهد و شیراز', changeFrequency: 'daily', priority: .9,
    description: 'تورهای داخلی و خارجی کارن تراول؛ تور کیش، مشهد، قشم، شیراز و تورهای خارجی با برنامهٔ سفر، هتل و حمل‌ونقل مشخص و امکان استعلام و رزرو آنلاین.'},
  {path: '/tours/last-minute', title: 'تور لحظه آخری', changeFrequency: 'daily', priority: .8,
    description: 'تورهای لحظه آخری کارن تراول با حرکت در دو هفتهٔ آینده و ظرفیت خالی؛ تاریخ حرکت، مدت سفر و مقصد هر تور را ببینید و پیش از تمام شدن ظرفیت رزرو کنید.'},
  {path: '/tours/nowruz', title: 'تور نوروزی', changeFrequency: 'daily', priority: .8,
    description: 'تورهای نوروزی کارن تراول برای تعطیلات پایان اسفند و نوروز؛ مقصدهای داخلی و خارجی، تاریخ حرکت و مدت سفر را مقایسه کنید یا درخواست تور نوروزی ثبت کنید.'},
  {path: '/tours/installment', title: 'خرید تور اقساطی', changeFrequency: 'weekly', priority: .7,
    description: 'خرید تور اقساطی در کارن تراول با سرویس‌های اقساطی همکار یا اقساط سازمانی؛ شرایط پیش‌پرداخت، تعداد اقساط و تورهای قابل خرید اقساطی را یک‌جا ببینید.'},
  {path: '/tours/special', title: 'تورهای ویژه و پیشنهادی', changeFrequency: 'daily', priority: .7,
    description: 'تورهای ویژهٔ کارن تراول که کارشناسان سفر برای این فصل انتخاب کرده‌اند؛ مقصد، مدت سفر و تاریخ حرکت تورهای پیشنهادی را ببینید و برای رزرو استعلام بگیرید.'},
  {path: '/tours/search', title: 'جست‌وجوی تور بر اساس مقصد', changeFrequency: 'daily', priority: .7,
    description: 'جست‌وجوی برنامهٔ تورهای کارن تراول بر اساس مقصد، دسته‌بندی، مدت و سال برگزاری؛ برنامهٔ روزبه‌روز هر تور را ببینید و قیمت و تاریخ جدید را استعلام کنید.'},
  {path: '/festival', title: 'جشنواره تور و سفر', changeFrequency: 'daily', priority: .6,
    description: 'جشنوارهٔ سفر کارن تراول با تورهای منتخب در بازهٔ برگزاری جشنواره؛ تاریخ شروع و پایان، شرایط و تورهای شامل جشنواره را ببینید یا درخواست سفر ثبت کنید.'},
  {path: '/destinations', title: 'راهنمای مقصدهای سفر در ایران', changeFrequency: 'weekly', priority: .8,
    description: 'راهنمای مقصدهای گردشگری ایران در کارن تراول؛ قشم، شیراز، یزد، ماسوله، اصفهان و شهرهای دیگر را بشناسید و تور، هتل و تجربه‌های هر مقصد را پیدا کنید.'},
  {path: '/experiences', title: 'تجربه‌های مقصد؛ گشت، راهنما و تفریح', changeFrequency: 'daily', priority: .7,
    description: 'تجربه‌های مقصد در کارن تراول؛ گشت شهری، راهنمای محلی، رستوران، رویداد، استخر و ورزش در شهرهای ایران را ببینید و برای رزرو یا استعلام اقدام کنید.'},
  {path: '/blog', title: 'مجله سفر و راهنمای گردشگری', changeFrequency: 'daily', priority: .7,
    description: 'مجلهٔ سفر کارن تراول؛ راهنمای مقصدها، نکات خرید بلیط هواپیما و رزرو هتل، تجربهٔ مسافران و پیشنهادهای سفر داخلی و خارجی برای برنامه‌ریزی بهتر سفر.'},
  {path: '/travel-guides', title: 'راهنمای سفر به شهرهای ایران', changeFrequency: 'weekly', priority: .6,
    description: 'راهنماهای سفر کارن تراول برای شهرهای ایران؛ بهترین زمان سفر، جاذبه‌های دیدنی، رفت‌وآمد و اقامت در هر مقصد را بخوانید و سفرتان را دقیق‌تر برنامه‌ریزی کنید.'},
  {path: '/visa', title: 'اخذ ویزا و راهنمای مدارک ویزا', changeFrequency: 'weekly', priority: .7,
    description: 'خدمات اخذ ویزای توریستی در کارن تراول؛ مدارک لازم، مدت بررسی و شرایط ویزای کشورهای پرمتقاضی را ببینید و درخواست ویزای خود را با کمک کارشناسان ثبت کنید.'},
  {path: '/car-rental', title: 'اجاره خودرو در سفر', changeFrequency: 'weekly', priority: .6,
    description: 'اجاره خودرو با راننده یا بدون راننده در شهرهای ایران با کارن تراول؛ نوع خودرو، تاریخ تحویل و محل تحویل را انتخاب کنید و درخواست اجاره ثبت کنید.'},
  {path: '/cruises', title: 'تور کروز و سفر دریایی', changeFrequency: 'weekly', priority: .5,
    description: 'تور کروز و سفرهای دریایی در کارن تراول؛ مسیرها، مدت سفر و امکانات کشتی‌های تفریحی را ببینید و برای رزرو سفر دریایی و کروز با کارشناسان ما استعلام بگیرید.'},
  {path: '/villas', title: 'اجاره ویلا و اقامتگاه بوم‌گردی', changeFrequency: 'weekly', priority: .7,
    description: 'اجاره ویلا، سوئیت و اقامتگاه بوم‌گردی در شمال، کیش و شهرهای دیگر با کارن تراول؛ ظرفیت، امکانات و قوانین هر اقامتگاه را پیش از رزرو مقایسه کنید.'},
  {path: '/restaurants', title: 'رستوران و کافه در مقصد سفر', changeFrequency: 'weekly', priority: .5,
    description: 'رستوران‌ها و کافه‌های منتخب در مقصدهای سفر با کارن تراول؛ غذای محلی و منوی هر مجموعه را ببینید و برای رزرو میز یا اطلاع از شرایط با ما تماس بگیرید.'},
  {path: '/attractions', title: 'جاذبه‌های گردشگری و تفریحی', changeFrequency: 'weekly', priority: .5,
    description: 'جاذبه‌های گردشگری و اماکن تفریحی شهرهای ایران در کارن تراول؛ موزه‌ها، بناهای تاریخی، پارک‌ها و تفریحات هر مقصد را بشناسید و بلیط یا بازدید را هماهنگ کنید.'},
  {path: '/events-venues', title: 'رزرو تالار و رویداد', changeFrequency: 'weekly', priority: .5,
    description: 'رزرو تالار، سالن همایش و مکان برگزاری رویداد با کارن تراول؛ ظرفیت، امکانات و شرایط هر مجموعه را ببینید و برای جشن، همایش یا رویداد سازمانی استعلام بگیرید.'},
  {path: '/pools-sports', title: 'رزرو استخر و مجموعه ورزشی', changeFrequency: 'weekly', priority: .5,
    description: 'رزرو استخر، باشگاه و مجموعه‌های ورزشی و تندرستی در سفر با کارن تراول؛ سانس‌ها، امکانات و شرایط استفاده را ببینید و برای خود یا کارکنان سازمان رزرو کنید.'},
  {path: '/handicrafts', title: 'خرید صنایع دستی ایران', changeFrequency: 'weekly', priority: .5,
    description: 'صنایع دستی اصیل شهرهای ایران در کارن تراول؛ فرش، سفال، مینا، قلم‌زنی و هنرهای محلی هر مقصد را بشناسید و سفارش یا خرید از هنرمندان را هماهنگ کنید.'},
  {path: '/souvenirs', title: 'سوغات شهرهای ایران', changeFrequency: 'weekly', priority: .5,
    description: 'سوغات شهرهای ایران در کارن تراول؛ سوغاتی مشهد، یزد، اصفهان، شیراز و شهرهای دیگر را بشناسید و برای خرید یا ارسال سوغات و هدیهٔ سفر سفارش ثبت کنید.'},
  {path: '/tourist-transport', title: 'ترانسفر فرودگاهی و حمل‌ونقل گردشگری', changeFrequency: 'weekly', priority: .5,
    description: 'ترانسفر فرودگاهی، ون و اتوبوس دربستی و حمل‌ونقل گردشگری در شهرهای ایران با کارن تراول؛ مسیر، تاریخ و تعداد مسافر را وارد کنید و درخواست ترانسفر ثبت کنید.'},
  {path: '/services', title: 'خدمات سفر؛ بیمه، ویزا، ترانسفر و اقامت', changeFrequency: 'weekly', priority: .7,
    description: 'همهٔ خدمات سفر کارن تراول در یک صفحه؛ بیمهٔ مسافرتی، ویزا، CIP، ترانسفر، اقامت، رستوران، گشت و خرید سفر، با وضعیت دسترسی و راه تماس روشن برای هر خدمت.'},
  {path: '/solutions', title: 'راهکارهای کارن تراول برای آژانس‌ها و سازمان‌ها', changeFrequency: 'monthly', priority: .5,
    description: 'سایت و اپ با برند خودتان، اتصال به تأمین‌کنندگان، قرارداد و صندوق، میز فروش، باشگاه مشتریان، پیامک و خروجی فرانگر برای آژانس‌ها و سازمان‌ها روی یک پرونده.'},
  {path: '/white-label', title: 'سایت اختصاصی خدمات سفر با برند شما', changeFrequency: 'monthly', priority: .4,
    description: 'سایت اختصاصی خدمات سفر با نام تجاری سازمان یا آژانس شما در کارن تراول؛ بلیط، هتل، تور و خدمات رفاهی کارکنان با برند خودتان. برای بررسی همکاری تماس بگیرید.'},
  {path: '/integrations', title: 'همکاری با کارن تراول؛ تأمین‌کنندگان سفر', changeFrequency: 'monthly', priority: .4,
    description: 'همکاری تأمین‌کنندگان خدمات اقامتی، حمل‌ونقل و تجربه‌های مقصد با کارن تراول؛ خدمات خود را معرفی کنید تا پس از بررسی و توافق در شبکهٔ کارن تراول عرضه شود.'},
  {path: '/assistant', title: 'دستیار هوشمند برنامه‌ریزی سفر', changeFrequency: 'monthly', priority: .5,
    description: 'دستیار هوشمند سفر کارن تراول؛ مقصد، بودجه و شرایطتان را بگویید تا گزینه‌های پرواز، هتل و تور را کنار هم بچیند و دلیل هر پیشنهاد را شفاف توضیح دهد.'},
  {path: '/compare', title: 'مقایسه پرواز، هتل و تور', changeFrequency: 'monthly', priority: .4,
    description: 'مقایسهٔ گزینه‌های سفر در کارن تراول؛ قیمت نهایی، قوانین کنسلی، امکانات و موقعیت پرواز، هتل و تور را کنار هم ببینید و آگاهانه بهترین گزینه را انتخاب کنید.'},
  {path: '/itineraries', title: 'برنامه‌ریز سفر و برنامه روزانه', changeFrequency: 'monthly', priority: .4,
    description: 'برنامه‌ریز سفر کارن تراول؛ برنامهٔ روزبه‌روز سفرتان را با پرواز، اقامت، گشت و رستوران بچینید و برای هماهنگی خدمات هر روز با کارشناسان سفر در تماس باشید.'},
  {path: '/reviews', title: 'نظرات مسافران دربارهٔ تورها و هتل‌ها', changeFrequency: 'weekly', priority: .4,
    description: 'نظرات تأییدشدهٔ مسافران کارن تراول دربارهٔ تورها، هتل‌ها و خدمات سفر؛ امتیاز هر خدمت، تجربهٔ واقعی مسافران با رزرو تأییدشده و پاسخ تأمین‌کننده را بخوانید.'},
  {path: '/faq', title: 'سؤالات متداول خرید بلیط، هتل و تور', changeFrequency: 'monthly', priority: .5,
    description: 'پاسخ سؤالات متداول مسافران کارن تراول دربارهٔ خرید بلیط هواپیما و قطار، رزرو هتل و تور، پرداخت، استرداد و تغییر رزرو و پیگیری درخواست‌ها از پشتیبانی.'},
  {path: '/support', title: 'پشتیبانی و مرکز راهنمایی سفر', changeFrequency: 'monthly', priority: .5,
    description: 'مرکز پشتیبانی کارن تراول؛ پیگیری رزرو، استرداد و تغییر بلیط، ثبت درخواست پشتیبانی و گفت‌وگو با کارشناس سفر پیش از سفر، در طول سفر و پس از بازگشت.'},
  {path: '/contact', title: 'تماس با کارن تراول و دربارهٔ ما', changeFrequency: 'monthly', priority: .5,
    description: 'راه‌های تماس با کارن تراول؛ تلفن پشتیبانی، ثبت درخواست مشاوره و استعلام خدمات سفر، همکاری سازمانی و پیگیری رزرو. کارشناسان ما پاسخگوی پرسش‌های شما هستند.'},
  {path: '/privacy', title: 'حریم خصوصی و حفاظت از اطلاعات', changeFrequency: 'yearly', priority: .2,
    description: 'سیاست حریم خصوصی کارن تراول؛ اطلاعاتی که هنگام خرید بلیط، رزرو هتل و تور از مسافران دریافت می‌شود، نحوهٔ نگهداری و استفاده از آن و حقوق شما دربارهٔ داده‌ها.'},
  {path: '/terms', title: 'قوانین و مقررات و شرایط استرداد', changeFrequency: 'yearly', priority: .2,
    description: 'قوانین و مقررات استفاده از خدمات کارن تراول؛ شرایط خرید بلیط، رزرو هتل و تور، قوانین استرداد و کنسلی، مسئولیت تأمین‌کنندگان و حقوق مسافران پیش از خرید.'},
];

const byPath = new Map(PUBLIC_PAGES.map(p => [p.path, p]));

/** Metadata for a fixed public page; throws at build time if the path has no row (keeps sitemap and pages in step). */
export function seoFor(path: string): Metadata {
  const p = byPath.get(path);
  if (!p) throw new Error(`lib/seo-pages.ts has no row for ${path}`);
  return pageMetadata(p);
}
