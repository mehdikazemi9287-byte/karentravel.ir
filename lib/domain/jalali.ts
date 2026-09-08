export type JalaliDate={jy:number;jm:number;jd:number};
export const jalaliMonths=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
export const persianDigits=(value:string|number)=>String(value).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
const div=(a:number,b:number)=>Math.floor(a/b);
export function jalaliToGregorian(jy:number,jm:number,jd:number){
 jy+=1595;let days=-355668+365*jy+div(jy,33)*8+div((jy%33+3),4)+jd+(jm<7?(jm-1)*31:(jm-7)*30+186);let gy=400*div(days,146097);days%=146097;
 if(days>36524){gy+=100*div(--days,36524);days%=36524;if(days>=365)days++}gy+=4*div(days,1461);days%=1461;if(days>365){gy+=div(days-1,365);days=(days-1)%365}
 const gd=days+1,leap=(gy%4===0&&gy%100!==0)||gy%400===0,md=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];let gm=1,left=gd;while(left>md[gm-1]){left-=md[gm-1];gm++}return {gy,gm,gd:left};
}
export function gregorianToJalali(gy:number,gm:number,gd:number):JalaliDate{
 const md=[0,31,28,31,30,31,30,31,31,30,31,30,31],leap=(gy%4===0&&gy%100!==0)||gy%400===0;let days=365*(gy-1600)+div(gy-1600+3,4)-div(gy-1600+99,100)+div(gy-1600+399,400)-80+gd;for(let i=1;i<gm;i++)days+=md[i]+(i===2&&leap?1:0);
 let jy=979+33*div(days,12053);days%=12053;jy+=4*div(days,1461);days%=1461;if(days>365){jy+=div(days-1,365);days=(days-1)%365}const jm=days<186?1+div(days,31):7+div(days-186,30),jd=1+(days<186?days%31:(days-186)%30);return {jy,jm,jd};
}
export const isoToJalali=(iso:string):JalaliDate=>{const [gy,gm,gd]=iso.split('-').map(Number);return gregorianToJalali(gy,gm,gd)};
export const jalaliToIso=(date:JalaliDate)=>{const g=jalaliToGregorian(date.jy,date.jm,date.jd);return `${g.gy.toString().padStart(4,'0')}-${g.gm.toString().padStart(2,'0')}-${g.gd.toString().padStart(2,'0')}`};
export const formatJalali=(iso:string)=>{if(!iso)return 'انتخاب تاریخ';const d=isoToJalali(iso);return `${persianDigits(d.jd)} ${jalaliMonths[d.jm-1]} ${persianDigits(d.jy)}`};
export const jalaliMonthLength=(jy:number,jm:number)=>jm<=6?31:jm<=11?30:(gregorianToJalali(jalaliToGregorian(jy,12,30).gy,jalaliToGregorian(jy,12,30).gm,jalaliToGregorian(jy,12,30).gd).jd===30?30:29);
export const todayIso=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`};
export const todayJalali=()=>isoToJalali(todayIso());