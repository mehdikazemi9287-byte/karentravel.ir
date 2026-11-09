import { ApiError } from './api/karenseir-client';

const GENERIC = 'ارتباط با سرویس انجام نشد.';

/** Server detail (always Persian in this API) for a rejected step; a generic line only when nothing came back. */
export function checkoutErrorMessage(error:unknown){
 if(error instanceof ApiError){
  if(error.status===503)return error.message&&error.message!==GENERIC?error.message:'سرویس موردنیاز فعلاً در دسترس نیست؛ کمی بعد دوباره تلاش کنید.';
  if(error.status>=400&&error.status<500&&error.message&&error.message!==GENERIC)return error.message;
  if([409,422].includes(error.status))return 'این مرحله قابل تأیید نیست؛ اطلاعات، قیمت یا شرایط رزرو تغییر کرده است. رزرو را بررسی کنید و در صورت نیاز با پشتیبانی تماس بگیرید.';
 }
 return 'ارتباط برقرار نشد. دوباره تلاش کنید؛ هیچ موفقیتی بدون دریافت پاسخ تأیید نمی‌شود.';
}
