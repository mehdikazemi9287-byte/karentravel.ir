/** Transport departure/arrival time for display. Data stays as given (UTC or supplier offset); only the display changes:
 *  - a UTC instant (Z / +00:00) is shown in Asia/Tehran time, labelled «به وقت تهران» (QA D10: no "UTC+00:00" for customers);
 *  - +03:30 is already Tehran time;
 *  - any other explicit offset keeps the supplier's local wall clock (e.g. an arrival abroad), labelled with that offset;
 *  - no offset: the supplier's wall clock as given, never guessed from the airport or the browser.
 *  Digits are Persian. */
const FA='۰۱۲۳۴۵۶۷۸۹';
const fa=(s:string)=>s.replace(/\d/g,n=>FA[+n]);
export function transportTime(value:unknown):{clock:string;date?:string;offset?:string;zoneLabel?:string;iso:string}|null {
  if(typeof value!=='string')return null;
  const raw=value.trim();
  const match=/^(?:(\d{4})-(\d{2})-(\d{2})[T ])?(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$/.exec(raw);
  if(!match)return null;
  const [,year,month,day,hour,minute,second,zone]=match;
  if(+hour>23||+minute>59||(second&&+second>59))return null;
  if(zone&&zone!=='Z'&&(+zone.slice(1,3)>23||+zone.slice(4)>59))return null;
  let date:string|undefined;
  if(year){
    const d=new Date(`${year}-${month}-${day}T12:00:00Z`);
    if(!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==`${year}-${month}-${day}`)return null;
    date=new Intl.DateTimeFormat('fa-IR',{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'}).format(d);
  }
  const iso=raw.replace(' ','T');
  const utc=zone==='Z'||zone==='+00:00'||zone==='-00:00';
  if(utc&&year){
    const instant=new Date(Date.UTC(+year,+month-1,+day,+hour,+minute,+(second||0)));
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Tehran',hourCycle:'h23',hour:'2-digit',minute:'2-digit'}).formatToParts(instant).map(p=>[p.type,p.value]));
    return {clock:fa(`${parts.hour}:${parts.minute}`),date:new Intl.DateTimeFormat('fa-IR',{year:'numeric',month:'short',day:'numeric',timeZone:'Asia/Tehran'}).format(instant),offset:'+03:30',zoneLabel:'به وقت تهران',iso};
  }
  if(utc){
    // A bare UTC clock without a date: shift by Tehran's fixed +03:30 (Iran has no daylight saving time since 1401/2022).
    const total=(+hour*60+ +minute+210)%1440;
    return {clock:fa(`${String(Math.floor(total/60)).padStart(2,'0')}:${String(total%60).padStart(2,'0')}`),offset:'+03:30',zoneLabel:'به وقت تهران',iso};
  }
  const zoneLabel=zone==='+03:30'?'به وقت تهران':zone?`به وقت محلی (UTC${fa(zone)})`:undefined;
  return {clock:fa(`${hour}:${minute}`),date,offset:zone,zoneLabel,iso};
}
