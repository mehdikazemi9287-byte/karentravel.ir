'use client';
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {RouteSimulator, type Stop} from './RouteSimulator';

type Tour = {id: string; title: string; origin: string; destination: string; details: Record<string, unknown>};

export function TourRouteView({id}: {id: string}) {
  const {api, session} = useAuth();
  const [tour, setTour] = useState<Tour | null>(null), [error, setError] = useState(false);
  useEffect(() => {let active = true; setError(false); (session ? api.get<Tour>(`/tour-products/${id}`) : api.publicGet<Tour>(`/public/tour-products/${id}`)).then(t => {if (active) setTour(t);}).catch(() => {if (active) setError(true);}); return () => {active = false;};}, [api, session, id]);
  const stops: Stop[] = Array.isArray(tour?.details.itinerary) ? (tour!.details.itinerary as unknown[]).flatMap(x => typeof x === 'string' ? [{title: x}] : x && typeof x === 'object' && typeof (x as Stop).title === 'string' ? [x as Stop] : []) : [];
  return <section className="customer-page tour-route-page">
    <Link href={`/tours/${id}`}>بازگشت به جزئیات تور</Link>
    <h1>شبیه‌ساز مسیر سفر{tour ? `: ${tour.title}` : ''}</h1>
    {tour && <p className="tour-route">{tour.origin} ← {tour.destination}</p>}
    {error ? <p role="alert">این تور در دسترس نیست. <Link href="/tours">جست‌وجوی تورها</Link></p> : !tour ? <p role="status">در حال دریافت…</p> : <RouteSimulator stops={stops} title={tour.title}/>}
  </section>;
}
