/** Preserve the supplier's wall clock. Never infer an airport or browser timezone. */
export function transportTime(value:unknown):{clock:string;date?:string;offset?:string;iso:string}|null {
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
  return {clock:`${hour}:${minute}`.replace(/\d/g,n=>'۰۱۲۳۴۵۶۷۸۹'[+n]),date,offset:zone==='Z'?'+00:00':zone,iso:raw.replace(' ','T')};
}
