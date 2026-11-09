const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const load=p=>{const scope={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,scope);return scope.exports};
const n=load('lib/national-code.ts');
for(const ok of ['0010350829','5260181591','۰۰۱۰۳۵۰۸۲۹','001-035-0829'])assert.ok(n.isValidNationalCode(ok),ok);
for(const bad of ['0010350828','1111111111','123456789','12345678901','abcdefghij',''])assert.ok(!n.isValidNationalCode(bad),bad);
assert.equal(n.normalizeDigits('۱۲۳ ٤٥٦'),'123456');
const s=load('lib/status-labels.ts');
for(const code of ['reserved','planned','awaiting_payment','confirmed','issued','cancelled','captured','overdue','something_new',undefined,null]){
  for(const f of [s.bookingStatusFa,s.tripStatusFa,s.moneyStatusFa,s.anyStatusFa])assert.ok(!/[A-Za-z_]/.test(f(code)),`${code} -> ${f(code)}`);
}
assert.equal(s.tripStatusFa('planned'),'برنامه‌ریزی‌شده');assert.equal(s.bookingStatusFa('reserved'),'نگه‌داشت موقت');
assert.equal(s.serviceTypeFa('train'),'قطار');assert.ok(!/[A-Za-z]/.test(s.serviceTypeFa('unknown_vertical')));
console.log('PASS national-code checksum (Persian digits, repeated digits) and Persian-only status/service labels');
