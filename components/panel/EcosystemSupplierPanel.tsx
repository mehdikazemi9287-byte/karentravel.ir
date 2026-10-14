'use client';
import {Async, Badge, Card, Table, money, useLoad} from './PanelKit';
type Supplier = {id: string; name: string};
type Row = {reservation_id: string; booking_reference: string | null; legal_name: string | null; provider_contract_id: string | null;
  settlements: {id: string; amount: number; currency: string; status: string}[]};
export function SupplierFinancialLinks() {
  const suppliers = useLoad<{supplier_records: Supplier[]}>('/supplier/dashboard');
  return <Async state={suppliers.state}>{d => d.supplier_records.map(s => <SupplierRows key={s.id} supplier={s}/>)}</Async>;
}
function SupplierRows({supplier}: {supplier: Supplier}) {
  const d = useLoad<{items: Row[]; total: number}>('/ecosystem/suppliers/' + encodeURIComponent(supplier.id) + '/financial-links');
  return <Card title={'روابط مالی ' + supplier.name}><Async state={d.state}>{x => <Table rows={x.items} rowKey={r => r.reservation_id}
    empty="رزرو مرتبط با قرارداد یا تسویه این تأمین‌کننده وجود ندارد." cols={[
      {label: 'رزرو', cell: r => r.booking_reference ?? r.reservation_id},
      {label: 'شرکت حقوقی', cell: r => r.legal_name ?? 'تعیین نشده'},
      {label: 'قرارداد تأمین', cell: r => r.provider_contract_id ?? 'ثبت نشده'},
      {label: 'تسویه', cell: r => r.settlements.length ? r.settlements.map(s => <p key={s.id}>{money(s.amount, s.currency)} <Badge status={s.status}/></p>) : 'تسویه‌ای ثبت نشده است'},
    ]}/>}</Async><p className="pn-muted">فقط اطلاعات همین تأمین‌کننده؛ اطلاعات پرداخت مشتری و سایر تأمین‌کنندگان نمایش داده نمی‌شود.</p></Card>;
}
