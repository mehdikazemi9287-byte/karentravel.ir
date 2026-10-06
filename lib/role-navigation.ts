// Navigation hints only. Every destination enforces tenant/RBAC in its API.
export const roleHome:Record<string,string>={customer:'/account',employee:'/employee',manager:'/organization',welfare_manager:'/organization',organization_admin:'/organization',supplier:'/supplier',agency_partner:'/agency',backoffice_expert:'/backoffice',finance_operator:'/finance',tenant_admin:'/admin',platform_admin:'/admin'};
export function roleLinks(role:string):Array<[string,string]>{
 const links:Array<[string,string]>=[['حساب و مسافران','/account'],['سفرها و رزروها','/trips'],['اعلان‌ها','/notifications'],['پشتیبانی','/support']];
 const home=roleHome[role];if(home&&home!=='/account')links.push(['پنل کاری من',home]);
 if(['organization_admin','tenant_admin','platform_admin'].includes(role))links.push(['مدیریت کاربران','/admin']);
 if(['tenant_admin','platform_admin'].includes(role))links.push(['عملیات سفر','/backoffice']);
 if(['platform_admin','backoffice_expert'].includes(role))links.push(['مدیریت هتل‌ها','/admin/catalog'],['مرکز عملیات سفر','/backoffice/trip-events']);
 if(role==='platform_admin')links.push(['امور مالی','/finance'],['تأمین‌کنندگان','/supplier']);
 return links.filter((item,index,all)=>all.findIndex(x=>x[1]===item[1])===index);
}
