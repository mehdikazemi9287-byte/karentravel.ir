'use client';
import {Async, Badge, Card, Table, money, useLoad} from './PanelKit';
type Invoice = {id: string; number: string; subtotal: number; tax: number; total: number; currency: string; status: string};
type Payment = {currency: string; captured: number; refunded: number; net_captured: number};
type Ledger = {id: string; entry_type: string; amount: number; currency: string | null; source_type: string; account_resolved: boolean};
type Installment = {id: string; status: string; principal: number; fee: number; total: number; currency: string};
type Settlement = {id: string; supplier_id: string | null; amount: number; currency: string; status: string};
type Data = {invoices: Invoice[]; payment_totals: Payment[]; funding_ledger: Ledger[]; installments: Installment[]; settlements?: Settlement[];
  price_components: {service_fee: number | null; discount: number; selling_total: number; tax: number} | null;
  supplier_settlement_calculation?: {currency: string; supplier_liability: number; allocated_settlement: number; remaining: number} | null;
  supplier_settlement_reason?: string; outstanding_reason: string};
const ENTRY: Record<string, string> = {allocate: 'تخصیص', reserve: 'مسدود', capture: 'مصرف', release: 'آزادسازی', reverse_capture: 'برگشت مصرف'};
const SOURCE: Record<string, string> = {organization_credit: 'اعتبار سازمان', credit: 'اعتبار', wallet: 'کیف پول'};
export function EcosystemFinancialDossier({reservationId}: {reservationId: string}) {
  const d = useLoad<Data>('/ecosystem/reservations/' + encodeURIComponent(reservationId) + '/finance');
  return <Async state={d.state}>{x => <>
    <Card title="صورتحساب"><Table rows={x.invoices} rowKey={r => r.id} empty="صورتحسابی ثبت نشده است." cols={[
      {label: 'شماره', cell: r => r.number}, {label: 'جمع', cell: r => money(r.total, r.currency)},
      {label: 'مالیات', cell: r => money(r.tax, r.currency)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>},
    ]}/></Card>
    <Card title="پرداخت ثبت‌شده"><Table rows={x.payment_totals} rowKey={r => r.currency} empty="پرداختی ثبت نشده است." cols={[
      {label: 'دریافت', cell: r => money(r.captured, r.currency)}, {label: 'بازپرداخت', cell: r => money(r.refunded, r.currency)},
      {label: 'خالص دریافت', cell: r => money(r.net_captured, r.currency)},
    ]}/></Card>
    <Card title="منابع اعتبار و کیف پول"><Table rows={x.funding_ledger} rowKey={r => r.id} empty="گردشی برای این رزرو ثبت نشده است." cols={[
      {label: 'منبع', cell: r => SOURCE[r.source_type] ?? r.source_type},
      {label: 'گردش', cell: r => ENTRY[r.entry_type] ?? r.entry_type},
      {label: 'مبلغ', cell: r => r.currency ? money(r.amount, r.currency) : 'ارز منبع مشخص نیست'},
      {label: 'مرجع', cell: r => r.account_resolved ? 'متصل' : 'نیازمند تطبیق'},
    ]}/></Card>
    <Card title="اقساط"><Table rows={x.installments} rowKey={r => r.id} empty="قرارداد اقساط ثبت نشده است." cols={[
      {label: 'اصل مبلغ', cell: r => money(r.principal, r.currency)}, {label: 'کارمزد', cell: r => money(r.fee, r.currency)},
      {label: 'جمع تعهد', cell: r => money(r.total, r.currency)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>},
    ]}/></Card>
    {x.settlements && <Card title="تسویه تأمین‌کننده"><Table rows={x.settlements} rowKey={r => r.id} empty="تسویه‌ای ثبت نشده است." cols={[
      {label: 'تأمین‌کننده', cell: r => r.supplier_id ?? 'نامشخص'},
      {label: 'مبلغ', cell: r => money(r.amount, r.currency)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>},
    ]}/>{x.supplier_settlement_calculation ? <p>مانده قابل تخصیص تسویه: {money(x.supplier_settlement_calculation.remaining, x.supplier_settlement_calculation.currency)}</p> : <p className="pn-muted">{x.supplier_settlement_reason}</p>}</Card>}
    <Card title="کنترل مانده"><p>{x.outstanding_reason}</p><p className="pn-muted">مصرف اعتبار، وجه دریافتی بانکی و مبلغ تسویه تأمین‌کننده سه مفهوم مستقل‌اند.</p></Card>
  </>}</Async>;
}
