'use client';
import {useState} from 'react';
import {EcosystemFinancialDossier} from './EcosystemFinancialDossier';
import {OrgScope} from './OrganizationPanel';
import {Async, Badge, Card, Stats, Table, fa, serviceFa, useLoad} from './PanelKit';

type LinkRow = {
  reservation_id: string; booking_reference: string | null; service_type: string;
  status: string; legal_name: string | null; licensed_entity_id: string | null;
  organization_id: string | null; request_id: string | null;
  provider_contract_id: string | null; provider_mode: string | null;
  relationship_gaps: string[]; organization_funding_authorized_by_link: false;
};
type Report = {items: LinkRow[]; total: number; limit: number; next_offset: number | null; read_only: true};
const GAP: Record<string, string> = {
  legal_entity_missing: 'شرکت حقوقی تعیین نشده',
  legal_entity_inactive: 'شرکت حقوقی فعال نیست',
  price_breakdown_missing: 'تفکیک قیمت ثبت نشده',
  provider_contract_unresolved: 'مرجع قرارداد تأمین در دسترس نیست',
  organization_funding_not_established_by_link: 'ارتباط سازمانی، مجوز پرداخت نیست',
};

export function EcosystemFinancialLinks({organizationId}: {organizationId?: string}) {
  const [selected, setSelected] = useState('');
  const [offset, setOffset] = useState(0);
  const path = organizationId
    ? '/ecosystem/organizations/' + encodeURIComponent(organizationId) + '/financial-links'
    : '/ecosystem/financial-links';
  const report = useLoad<Report>(path + '?offset=' + offset);
  return <Async state={report.state}>{data => <>
    <Stats items={[
      {label: 'رزروهای مرتبط', value: fa(data.total)},
      {label: 'نمایش فعلی', value: fa(data.items.length), hint: 'آخرین ' + fa(data.limit) + ' رزرو'},
      {label: 'تعهد سازمان', value: 'نیازمند مجوز مستقل'},
    ]}/>
    <Card title={organizationId ? 'روابط مالی سفرهای سازمان' : 'روابط مالی اکوسیستم'}>
      <Table rows={data.items} rowKey={r => r.reservation_id}
        empty="رزروی برای بررسی روابط مالی وجود ندارد."
        cols={[
          {label: 'رزرو', cell: r => <span><button type="button" className="pn-btn ghost" onClick={() => setSelected(r.reservation_id)}>پرونده مالی</button><br/>{r.booking_reference ?? r.reservation_id}<br/>{serviceFa(r.service_type)} <Badge status={r.status}/></span>},
          {label: 'شرکت حقوقی', cell: r => r.legal_name ?? 'تعیین نشده'},
          {label: 'درخواست سازمان', cell: r => r.request_id ?? 'بدون ارتباط سازمانی'},
          {label: 'قرارداد تأمین', cell: r => r.provider_contract_id ? <span>{r.provider_contract_id}<br/>{r.provider_mode}</span> : 'ثبت نشده'},
          {label: 'وضعیت اتصال', cell: r => r.relationship_gaps.length ? r.relationship_gaps.map(g => <p key={g}>{GAP[g] ?? 'نیازمند بررسی'}</p>) : 'روابط ثبت‌شده؛ صحت تجاری نیازمند بررسی'},
        ]}/>
    </Card>
    <div className="pn-form"><button type="button" className="pn-btn ghost" disabled={offset === 0} onClick={() => {setSelected(''); setOffset(Math.max(0, offset - data.limit));}}>قبلی</button><button type="button" className="pn-btn ghost" disabled={data.next_offset === null} onClick={() => {setSelected(''); setOffset(data.next_offset ?? offset);}}>بعدی</button></div>
    {selected && <EcosystemFinancialDossier reservationId={selected}/>}
    <Card title="وضعیت و دسترسی">
      <p>ارتباط سازمان با رزرو، مجوز برداشت از اعتبار سازمان نیست.</p>
      <p className="pn-muted">این بخش فقط خواندنی است؛ ثبت و تسویه در مسیرهای مجاز انجام می‌شود. وجود قرارداد، اتصال زنده وب‌سرویس را تأیید نمی‌کند.</p>
    </Card>
  </>}</Async>;
}

export function OrganizationFinancialLinks() {return <OrgScope>{org => <EcosystemFinancialLinks key={org.id} organizationId={org.id}/>}</OrgScope>;}
