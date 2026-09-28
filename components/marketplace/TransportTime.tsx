import { transportTime } from '../../lib/transport-time';

export function TransportTime({value,fallback='زمان اعلام نشده'}:{value:unknown;fallback?:string}) {
  const parts=transportTime(value);
  if(!parts)return <time>{fallback}</time>;
  return <time className="transport-time" dateTime={parts.iso}>
    <strong dir="ltr">{parts.clock}</strong>
    {parts.date&&<span>{parts.date}</span>}
    <small dir={parts.offset?'ltr':'rtl'}>{parts.offset?'UTC'+parts.offset:'منطقهٔ زمانی اعلام نشده'}</small>
  </time>;
}
