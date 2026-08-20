import type { MerchantRelation } from '../../lib/domain/travel';
export function CreditBadge(){return <span className="credit-badge" title="امکان بررسی اعتبار شخصی یا سازمانی پس از استعلام معتبر"><i aria-hidden="true">ک</i> اعتبارپذیر</span>}
export function PartnerBadge({relation}:{relation:MerchantRelation}){if(relation==='external')return <span className="source-badge">مکان عمومی</span>;if(relation==='credit-enabled')return <CreditBadge/>;return <span className="partner-badge">شریک نمونه</span>}
export function StatusBadge({status}:{status:string}){const labels:Record<string,string>={confirmed:'تأییدشده',pending:'در انتظار',issued:'صادرشده',completed:'تکمیل‌شده',cancelled:'لغوشده'};return <span className={`status-badge status-${status}`}>{labels[status]??status}</span>}
