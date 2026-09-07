'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError, newId } from '../../lib/api/karenseir-client';
import { Shell } from '../../app/page';

const money = (value: number) => `${value.toLocaleString('fa-IR')} ریال`;
function failure(error: unknown) { return error instanceof ApiError ? `${error.status}: ${error.message}` : 'خطای پیش‌بینی‌نشده رخ داد.'; }
const verticalLabels: Record<string, string> = { restaurant: 'رستوران و کافه', event_hall: 'رویداد و تالار', pool_sport: 'استخر و ورزش', attraction: 'اماکن گردشگری و تفریحی' };

type TicketType = { id: string; code: string; label: string; price: number; currency: string; quota: number | null; active: boolean };
type SessionRow = { id: string; starts_at: string; ends_at: string; capacity_available: number; status: string };
type Place = { id: string; name: string; city: string; address: string | null };
type Product = { id: string; title: string; description: string; service_type: string; booking_mode: string };
type Detail = { place: Place | null; product: Product; sessions: SessionRow[]; ticket_types: TicketType[] };
type PriceCheckResult = { id: string; amount: number; currency: string; expires_at: string; ticket_breakdown: Array<{ code: string; label: string; unit_price: number; quantity: number; subtotal: number }> };

export function ExperienceProductView({ productId }: { productId: string }) {
  const { api, session } = useAuth();
  const router = useRouter();
  const [detail, setDetail] = useState<Detail | null | undefined>();
  const [notice, setNotice] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [priceCheck, setPriceCheck] = useState<PriceCheckResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!session) return;
    let active = true;
    api.get<Detail>(`/experience-products/${productId}`).then(data => { if (active) { setDetail(data); setSessionId(data.sessions[0]?.id || ''); } }).catch(error => { if (active) { setDetail(null); setNotice(failure(error)); } });
    return () => { active = false; };
  }, [api, productId, session]);

  function setQuantity(ticketTypeId: string, value: number) { setQuantities(current => ({ ...current, [ticketTypeId]: Math.max(0, value) })); setPriceCheck(null); }

  async function runPriceCheck() {
    const selections = Object.entries(quantities).filter(([, quantity]) => quantity > 0).map(([ticket_type_id, quantity]) => ({ ticket_type_id, quantity }));
    if (!sessionId || selections.length === 0) { setNotice('حداقل یک بلیت را انتخاب کنید.'); return; }
    setBusy(true); setNotice('');
    try {
      const result = await api.post<PriceCheckResult>(`/leisure-sessions/${sessionId}/price-check`, { selections, command_id: newId() });
      setPriceCheck(result);
    } catch (error) { setNotice(failure(error)); } finally { setBusy(false); }
  }

  async function confirmReservation() {
    if (!priceCheck) return;
    setBusy(true); setNotice('');
    try {
      const reservation = await api.post<{ id: string }>('/orchestration/bookings', { price_check_id: priceCheck.id, command_id: newId() });
      router.push(`/checkout/${reservation.id}`);
    } catch (error) { setNotice(failure(error)); } finally { setBusy(false); }
  }

  if (!session) return <Shell><div className="ref-container" style={{ paddingTop: 24 }}><p className="panel">برای مشاهده جزئیات و رزرو <Link href="/login">وارد شوید</Link>.</p></div></Shell>;
  if (detail === undefined) return <Shell><div className="ref-container" style={{ paddingTop: 24 }}>در حال دریافت اطلاعات…</div></Shell>;
  if (!detail) return <Shell><div className="ref-container" style={{ paddingTop: 24 }}><p className="panel">{notice || 'این خدمت پیدا نشد.'}</p></div></Shell>;

  const { place, product, sessions, ticket_types: ticketTypes } = detail;

  return <Shell><div className="ref-container" style={{ paddingTop: 24, paddingBottom: 40 }}>
    <span className="eyebrow">{verticalLabels[product.service_type] ?? product.service_type}</span>
    <h1>{product.title}</h1>
    {place && <p>{place.name} · {place.city}{place.address ? ` · ${place.address}` : ''}</p>}
    {product.description && <p>{product.description}</p>}
    {notice && <p role="status" className="results-notice">{notice}</p>}

    <section className="panel" style={{ marginTop: 20 }}>
      <h2>تاریخ و سانس</h2>
      {sessions.length === 0 ? <p>در حال حاضر سانس فعالی برای این خدمت ثبت نشده است.</p> : <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
        {sessions.map(row => <button type="button" key={row.id} onClick={() => { setSessionId(row.id); setPriceCheck(null); }} className={sessionId === row.id ? 'active' : ''} style={{ padding: '8px 14px', borderRadius: 10, border: '1px solid var(--line)', background: sessionId === row.id ? 'var(--ink)' : '#fff', color: sessionId === row.id ? '#fff' : 'inherit' }}>
          {new Date(row.starts_at).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })} · {row.capacity_available.toLocaleString('fa-IR')} ظرفیت باقی‌مانده
        </button>)}
      </div>}
    </section>

    <section className="panel" style={{ marginTop: 16 }}>
      <h2>نوع بلیت</h2>
      {ticketTypes.length === 0 ? <p>بلیتی برای این خدمت تعریف نشده است.</p> : <div style={{ marginTop: 10 }}>
        {ticketTypes.map(ticketType => <div key={ticketType.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--line)' }}>
          <span><b>{ticketType.label}</b><small style={{ display: 'block', color: 'var(--muted)' }}>{money(ticketType.price)}</small></span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button type="button" onClick={() => setQuantity(ticketType.id, (quantities[ticketType.id] || 0) - 1)} aria-label={`کاهش ${ticketType.label}`}>−</button>
            <b>{quantities[ticketType.id] || 0}</b>
            <button type="button" onClick={() => setQuantity(ticketType.id, (quantities[ticketType.id] || 0) + 1)} aria-label={`افزایش ${ticketType.label}`}>+</button>
          </span>
        </div>)}
      </div>}
      <button className="button primary" style={{ marginTop: 16 }} disabled={busy || sessions.length === 0 || ticketTypes.length === 0} onClick={() => void runPriceCheck()}>بررسی قیمت</button>
    </section>

    {priceCheck && <section className="panel" style={{ marginTop: 16 }}>
      <h2>جمع‌بندی قیمت</h2>
      {priceCheck.ticket_breakdown.map(row => <p key={row.code}>{row.label} × {row.quantity.toLocaleString('fa-IR')} = {money(row.subtotal)}</p>)}
      <p><b>مبلغ نهایی: {money(priceCheck.amount)}</b></p>
      <button className="button primary" disabled={busy} onClick={() => void confirmReservation()}>تأیید و رزرو</button>
    </section>}
  </div></Shell>;
}
