/* Persian labels for status and service codes shown in customer views.
 * Customer pages must never print an English code: unknown values fall back to a neutral Persian label. */

export const BOOKING_STATUS_FA: Record<string, string> = {
  booking_pending: 'در انتظار پاسخ میزبان', reserved: 'نگه‌داشت موقت', held: 'نگه‌داشت موقت', draft: 'پیش‌نویس', pending: 'در انتظار تکمیل',
  awaiting_payment: 'در حال تکمیل رزرو', pending_payment: 'منتظر پرداخت', awaiting_fulfillment: 'در انتظار صدور مدارک', confirmed: 'تأیید شده',
  issued: 'مدارک صادر شده', changed: 'تغییر ثبت شده', cancelled: 'لغو شده', canceled: 'لغو شده', expired: 'مهلت پایان یافته', failed: 'تکمیل نشده',
  cancel_requested: 'درخواست کنسلی در حال بررسی', change_requested: 'درخواست تغییر در حال بررسی', refund_requested: 'درخواست استرداد در حال بررسی',
  refunded: 'استرداد ثبت شده', completed: 'انجام‌شده', fulfilled: 'انجام‌شده', used: 'استفاده‌شده',
};

export const TRIP_STATUS_FA: Record<string, string> = {
  planned: 'برنامه‌ریزی‌شده', active: 'در جریان', in_progress: 'در جریان', upcoming: 'پیش رو', completed: 'انجام‌شده', cancelled: 'لغو شده', archived: 'بایگانی‌شده',
};

export const MONEY_STATUS_FA: Record<string, string> = {
  created: 'ایجاد شده', initiated: 'در حال پرداخت', authorized: 'تأیید بانک', captured: 'پرداخت‌شده', paid: 'پرداخت‌شده', failed: 'ناموفق', refunded: 'مستردشده',
  issued: 'صادرشده', draft: 'پیش‌نویس', void: 'باطل‌شده', voided: 'باطل‌شده', overdue: 'سررسید گذشته', active: 'فعال', approved: 'تأییدشده',
  pending_approval: 'در انتظار تأیید', rejected: 'ردشده', settled: 'تسویه‌شده', closed: 'بسته‌شده', defaulted: 'معوق',
};

export const SERVICE_TYPE_FA: Record<string, string> = {
  flight: 'پرواز', hotel: 'هتل', train: 'قطار', bus: 'اتوبوس', tour: 'تور', package: 'پرواز + هتل', accommodation: 'اقامتگاه', vacation_rental: 'ویلا و اقامتگاه',
  car_rental: 'اجاره خودرو', cruise: 'سفر دریایی', visa: 'ویزا', insurance: 'بیمه', cip: 'تشریفات فرودگاهی', transfer: 'ترانسفر', restaurant: 'رستوران و کافه',
  event_hall: 'رویداد و تالار', pool_sport: 'استخر و ورزش', attraction: 'اماکن گردشگری و تفریحی', handicraft: 'صنایع‌دستی', travel_guide: 'راهنمای سفر',
  tourist_transportation: 'حمل‌ونقل گردشگری',
};

const pick = (map: Record<string, string>, fallback: string) => (code?: string | null) => (code && map[code.toLowerCase()]) || fallback;

export const bookingStatusFa = pick(BOOKING_STATUS_FA, 'در حال پیگیری');
export const tripStatusFa = pick({...BOOKING_STATUS_FA, ...TRIP_STATUS_FA}, 'در حال پیگیری');
export const moneyStatusFa = pick(MONEY_STATUS_FA, 'در حال پیگیری');
export const serviceTypeFa = pick(SERVICE_TYPE_FA, 'خدمت سفر');
/** Any customer-facing status (booking, trip, payment, invoice, installment). */
export const anyStatusFa = pick({...MONEY_STATUS_FA, ...BOOKING_STATUS_FA, ...TRIP_STATUS_FA}, 'در حال پیگیری');
