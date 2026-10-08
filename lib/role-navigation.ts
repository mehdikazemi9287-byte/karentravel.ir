// Navigation hints only. Every destination enforces tenant/RBAC in its API.
export const roleHome:Record<string,string>={customer:'/account',employee:'/employee',manager:'/organization',welfare_manager:'/organization',organization_admin:'/organization',supplier:'/supplier',agency_partner:'/agency',backoffice_expert:'/backoffice',finance_operator:'/finance',tenant_admin:'/admin',platform_admin:'/admin'};
export function roleLinks(role:string):Array<[string,string]>{
 const links:Array<[string,string]>=[['حساب من','/account'],['رزروها و سفرها','/account/bookings'],['اعلان‌ها','/account/notifications'],['پشتیبانی','/account/support']];
 const home=roleHome[role];if(home&&home!=='/account')links.push(['پنل کاری من',home]);
 if(['organization_admin','tenant_admin','platform_admin'].includes(role))links.push(['مدیریت کاربران','/admin']);
 if(['tenant_admin','platform_admin'].includes(role))links.push(['عملیات سفر','/backoffice']);
 if(['platform_admin','backoffice_expert'].includes(role))links.push(['مدیریت هتل‌ها','/admin/catalog'],['تورهای مرجع','/admin/tours'],['داده‌های مرجع','/admin/catalog/reference'],['مرکز عملیات سفر','/backoffice/trip-events'],['میز پشتیبانی','/backoffice/support'],['وضعیت اعلان‌ها','/backoffice/notifications']);
 if(['platform_admin','finance_operator'].includes(role))links.push(['رکوردهای مالی','/finance/records'],['حسابداری و کمیسیون','/finance/accounting']);
 if(['platform_admin','tenant_admin'].includes(role))links.push(['تأمین‌کنندگان و آژانس‌ها','/admin/partners'],['سازمان‌ها','/admin/organizations'],['سوابق ممیزی','/admin/audit']);
 if(['customer','employee'].includes(role))links.push(['پیشنهادهای قیمت','/quotes']);
 if(['platform_admin','supplier'].includes(role))links.push(['تسویه و قراردادها','/supplier/settlements'],['هتل‌های من','/supplier/hotels']);
 if(role==='platform_admin')links.push(['امور مالی','/finance'],['تأمین‌کنندگان','/supplier']);
 return links.filter((item,index,all)=>all.findIndex(x=>x[1]===item[1])===index);
}
