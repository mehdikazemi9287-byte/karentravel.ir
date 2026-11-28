/** Today's date (YYYY-MM-DD) on the Tehran calendar, whatever the browser's zone. Flight dates are Tehran dates:
 *  between 00:00 and 03:30 Tehran time the UTC date is still yesterday (QA 2026-11-28). */
export function tehranToday(now: Date = new Date()): string {
  return now.toLocaleDateString('en-CA', {timeZone: 'Asia/Tehran'});
}
