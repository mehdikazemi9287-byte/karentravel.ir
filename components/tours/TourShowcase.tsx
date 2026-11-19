'use client';
/* Stitch round 6 — mobile/08 «Tour 360 Showcase». Organiser-supplied equirectangular images only; no stock or invented media. */
import {useRef, useState} from 'react';
import './tours-round6.css';

type Hotspot = {label: string; yaw: number};
type Scene = {url: string; title?: string; hotspots?: Hotspot[]};
type Narration = {title: string; guide?: string; audio_url?: string | null};

export function TourShowcase({details}: {details: Record<string, unknown>}) {
  const scenes = (Array.isArray(details.media_360) ? details.media_360 : []).filter((s): s is Scene => !!s && typeof s === 'object' && typeof (s as Scene).url === 'string');
  const narration = details.narration && typeof details.narration === 'object' && typeof (details.narration as Narration).title === 'string' ? details.narration as Narration : null;
  const [index, setIndex] = useState(0);
  const [yaw, setYaw] = useState(0);
  const drag = useRef<{x: number; yaw: number} | null>(null);
  if (scenes.length === 0 && !narration) return null;
  const scene = scenes[Math.min(index, scenes.length - 1)];
  const norm = (v: number) => ((v % 360) + 360) % 360;
  const turn = (delta: number) => setYaw(v => norm(v + delta));
  return <section className="tour-showcase" aria-label="نمای ۳۶۰ درجه تور">
    {scene && <>
      <div className="ts-viewer" role="img" aria-label={scene.title || 'تصویر ۳۶۰ درجه'} tabIndex={0}
        style={{backgroundImage: `url("${scene.url.replace(/"/g, '')}")`, backgroundPositionX: `${-(yaw / 360) * 100 * 4}%`}}
        onPointerDown={e => {drag.current = {x: e.clientX, yaw}; (e.target as HTMLElement).setPointerCapture?.(e.pointerId);}}
        onPointerMove={e => {if (drag.current) setYaw(norm(drag.current.yaw - (e.clientX - drag.current.x) * 0.4));}}
        onPointerUp={() => {drag.current = null;}} onPointerCancel={() => {drag.current = null;}}
        onKeyDown={e => {if (e.key === 'ArrowLeft') turn(15); if (e.key === 'ArrowRight') turn(-15);}}>
        {(scene.hotspots || []).map(h => {const rel = ((norm(h.yaw - yaw) + 180) % 360) - 180; return Math.abs(rel) < 70 ? <span key={h.label} className="ts-hotspot" style={{insetInlineStart: `${50 - rel / 1.4}%`}}><i aria-hidden="true"/>{h.label}</span> : null;})}
        <span className="ts-angle">زاویه: {Math.round(yaw).toLocaleString('fa-IR')}°</span>
        <span className="ts-hint">برای چرخش ۳۶۰ درجه به طرفین بکشید</span>
        <div className="ts-controls"><button type="button" aria-label="چرخش به راست" onClick={() => turn(-45)}>›</button><button type="button" aria-label="چرخش به چپ" onClick={() => turn(45)}>‹</button></div>
      </div>
      {scenes.length > 1 && <div className="ts-scenes" role="tablist" aria-label="صحنه‌ها">{scenes.map((s, i) => <button key={s.url} role="tab" aria-selected={i === index} onClick={() => {setIndex(i); setYaw(0);}}>{s.title || `صحنهٔ ${(i + 1).toLocaleString('fa-IR')}`}</button>)}</div>}
    </>}
    {narration && <div className="ts-narration"><div><b>{narration.title}</b>{narration.guide && <small>روایت: {narration.guide}</small>}</div>
      {narration.audio_url ? <audio controls preload="none" src={narration.audio_url}>پخش صوت در این مرورگر پشتیبانی نمی‌شود.</audio> : <small className="ts-muted">فایل صوتی روایت هنوز توسط برگزارکننده بارگذاری نشده است.</small>}</div>}
  </section>;
}
