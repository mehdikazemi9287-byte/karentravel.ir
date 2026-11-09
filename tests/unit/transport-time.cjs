const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync('lib/transport-time.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const scope={exports:{},Intl,Date};vm.runInNewContext(code,scope);const f=scope.exports.transportTime;
for(const tz of ['UTC','America/Los_Angeles','Asia/Tokyo']){
 process.env.TZ=tz;
 const a=f('2027-02-11T00:15:00+03:30');assert.equal(a.clock,'۰۰:۱۵');assert.equal(a.offset,'+03:30');assert.equal(a.date,new Intl.DateTimeFormat('fa-IR',{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'}).format(new Date('2027-02-11T12:00:00Z')));
 assert.equal(f('2027-02-11T23:45:00-07:00').clock,'۲۳:۴۵');assert.equal(f('2027-02-11T23:45:00-07:00').offset,'-07:00');
 const u=f('2027-02-11T09:00:00Z');assert.equal(u.offset,'+03:30');assert.equal(u.clock,'۱۲:۳۰');assert.equal(u.zoneLabel,'به وقت تهران');assert.ok(!/UTC/.test(u.zoneLabel));
 const late=f('2027-02-11T22:00:00+00:00');assert.equal(late.clock,'۰۱:۳۰');assert.equal(late.date,new Intl.DateTimeFormat('fa-IR',{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'}).format(new Date('2027-02-12T12:00:00Z')));
 const summer=f('2027-07-01T04:00:00Z');assert.equal(summer.clock,'۰۷:۳۰');
 assert.equal(a.zoneLabel,'به وقت تهران');assert.equal(f('2027-02-11T23:45:00-07:00').zoneLabel,'به وقت محلی (UTC-۰۷:۰۰)');
}
assert.equal(f('09:30').clock,'۰۹:۳۰');assert.equal(f('09:30').zoneLabel,undefined);assert.equal(f('20:45Z').clock,'۰۰:۱۵');assert.equal(f('09:30').offset,undefined);assert.equal(f('2027-02-11 09:30').offset,undefined);
for(const v of [null,42,'','unknown','2027-02-30T09:30:00Z','2027-13-01T09:30:00Z','24:00','09:60','09:00:60','09:00+03:99'])assert.equal(f(v),null);
assert.ok(f('2028-02-29T09:30:00.123+03:30'));
console.log('PASS: UTC shown as Tehran time with Persian digits; supplier offsets preserved across browser zones; missing/invalid/leap-day inputs');
