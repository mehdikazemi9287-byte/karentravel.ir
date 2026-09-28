export function rentalRangeError(start:string,end:string){
 const valid=(value:string)=>/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value+'T12:00:00Z'))&&new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value;
 if(!valid(start)||!valid(end))return 'تاریخ تحویل و بازگشت خودرو را کامل و معتبر انتخاب کنید.';
 if(end<start)return 'تاریخ بازگشت خودرو نمی‌تواند پیش از تاریخ تحویل باشد.';
 return '';
}
