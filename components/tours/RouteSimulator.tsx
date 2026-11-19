'use client';
/* Stitch round 6 — desktop/15 «شبیه‌ساز مسیر پرواز و ترانسفر». Draws only the organiser's itinerary stops that carry real coordinates. */
import {useEffect, useMemo, useRef, useState} from 'react';
import './tours-round6.css';

export type Stop = {title: string; place?: string; day?: number; time?: string; mode?: string; note?: string; lat?: number; lng?: number};
const MODE_FA: Record<string, string> = {flight: 'پرواز', road: 'زمینی', rail: 'ریلی', walk: 'پیاده', stay: 'اقامت', activity: 'برنامه'};
const W = 1000, H = 560, PAD = 70;

export function RouteSimulator({stops: raw, title}: {stops: Stop[]; title?: string}) {
  const stops = useMemo(() => raw.filter(s => typeof s.lat === 'number' && typeof s.lng === 'number'), [raw]);
  const [progress, setProgress] = useState(0); // 0..stops.length-1
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const last = useRef<number | null>(null);
  const points = useMemo(() => {
    if (stops.length === 0) return [];
    const lats = stops.map(s => s.lat as number), lngs = stops.map(s => s.lng as number);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
    const spanLng = Math.max(maxLng - minLng, 0.5), spanLat = Math.max(maxLat - minLat, 0.5);
    const k = Math.min((W - 2 * PAD) / spanLng, (H - 2 * PAD) / spanLat);
    const ox = (W - spanLng * k) / 2, oy = (H - spanLat * k) / 2;
    // RTL map is still geographic: east is right.
    const raw = stops.map(s => ({x: ox + ((s.lng as number) - minLng) * k, y: oy + (maxLat - (s.lat as number)) * k}));
    // Stops at the same place (e.g. return to origin) are fanned out so both stay visible and clickable.
    return raw.map((p, i) => {const same = raw.slice(0, i).filter(q => Math.hypot(q.x - p.x, q.y - p.y) < 6).length; return same ? {x: p.x + same * 34, y: p.y + same * 30} : p;});
  }, [stops]);
  const max = Math.max(0, points.length - 1);
  useEffect(() => {
    if (!playing) {last.current = null; return;}
    let raf = 0;
    const tick = (t: number) => {
      if (last.current !== null) setProgress(p => {const n = p + ((t - last.current!) / 2500) * speed; if (n >= max) {setPlaying(false); return max;} return n;});
      last.current = t; raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, max]);
  if (points.length < 2) return <div className="route-sim empty"><b>شبیه‌ساز مسیر هنوز آماده نیست</b><p>برای نمایش مسیر، برگزارکننده باید دست‌کم دو توقف برنامهٔ سفر را با مختصات جغرافیایی ثبت کند.</p></div>;
  const seg = Math.min(Math.floor(progress), max - 1), frac = progress - seg;
  const a = points[seg], b = points[seg + 1];
  const curve = (p: {x: number; y: number}, q: {x: number; y: number}, flight: boolean) => {const mx = (p.x + q.x) / 2, my = (p.y + q.y) / 2 - (flight ? Math.hypot(q.x - p.x, q.y - p.y) * 0.25 : 0); return {mx, my};};
  const isFlight = (i: number) => stops[i + 1]?.mode === 'flight' || stops[i]?.mode === 'flight';
  const {mx, my} = curve(a, b, isFlight(seg));
  const bez = (t: number) => ({x: (1 - t) ** 2 * a.x + 2 * (1 - t) * t * mx + t * t * b.x, y: (1 - t) ** 2 * a.y + 2 * (1 - t) * t * my + t * t * b.y});
  const marker = progress >= max ? points[max] : bez(frac);
  const current = Math.min(Math.round(progress), max);
  const jump = (i: number) => {setPlaying(false); setProgress(Math.max(0, Math.min(max, i)));};
  return <section className="route-sim" aria-label="شبیه‌ساز مسیر سفر">
    <div className="rs-stage">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`مسیر ${title || 'تور'} در ${points.length.toLocaleString('fa-IR')} توقف`}>
        <defs><linearGradient id="rs-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f6e7d6"/><stop offset="1" stopColor="#ead3bd"/></linearGradient></defs>
        <rect width={W} height={H} rx="28" fill="url(#rs-sky)"/>
        {points.slice(0, -1).map((p, i) => {const q = points[i + 1]; const c = curve(p, q, isFlight(i)); return <path key={i} d={`M${p.x},${p.y} Q${c.mx},${c.my} ${q.x},${q.y}`} className={`rs-leg ${isFlight(i) ? 'flight' : 'ground'} ${i < seg || progress >= max ? 'done' : ''}`}/>;})}
        {points.map((p, i) => <g key={i} className={`rs-stop ${i === current ? 'now' : ''} ${i < progress ? 'past' : ''}`} onClick={() => jump(i)} tabIndex={0} role="button" aria-label={`توقف ${(i + 1).toLocaleString('fa-IR')}: ${stops[i].place || stops[i].title}`} onKeyDown={e => {if (e.key === 'Enter') jump(i);}}>
          <circle cx={p.x} cy={p.y} r="14"/><text x={p.x} y={p.y + 5} textAnchor="middle">{(i + 1).toLocaleString('fa-IR')}</text>
          <text className="rs-label" x={p.x} y={p.y - 24} textAnchor="middle">{stops[i].place || stops[i].title}</text></g>)}
        <g className="rs-marker" transform={`translate(${marker.x},${marker.y})`}><circle r="11"/><text y="5" textAnchor="middle">{isFlight(seg) ? '✈' : '●'}</text></g>
      </svg>
      <div className="rs-hud"><b>{stops[current].title}</b><span>{stops[current].day ? `روز ${stops[current].day!.toLocaleString('fa-IR')}` : ''}{stops[current].time ? ` · ${stops[current].time}` : ''}{stops[current].mode ? ` · ${MODE_FA[stops[current].mode!] || ''}` : ''}</span></div>
    </div>
    <div className="rs-controls">
      <button type="button" className="rs-play" onClick={() => {if (progress >= max) setProgress(0); setPlaying(p => !p);}} aria-pressed={playing}>{playing ? '❚❚ توقف' : '▶ پخش مسیر'}</button>
      <button type="button" onClick={() => jump(Math.ceil(progress) - 1)} disabled={progress <= 0}>توقف قبلی</button>
      <button type="button" onClick={() => jump(Math.floor(progress) + 1)} disabled={progress >= max}>توقف بعدی</button>
      <input type="range" min={0} max={max} step={0.01} value={progress} aria-label="پیشرفت مسیر" onChange={e => {setPlaying(false); setProgress(Number(e.target.value));}}/>
      <div className="rs-speed" role="group" aria-label="سرعت">{[1, 2, 4].map(s => <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s.toLocaleString('fa-IR')}×</button>)}</div>
    </div>
    <ol className="rs-timeline">{stops.map((s, i) => <li key={i} className={i === current ? 'now' : i < progress ? 'past' : ''}><button type="button" onClick={() => jump(i)}><b>{(i + 1).toLocaleString('fa-IR')}. {s.title}</b><small>{[s.day ? `روز ${s.day.toLocaleString('fa-IR')}` : '', s.time, s.mode ? MODE_FA[s.mode] : '', s.place].filter(Boolean).join(' · ')}</small>{s.note && <span>{s.note}</span>}</button></li>)}</ol>
  </section>;
}
