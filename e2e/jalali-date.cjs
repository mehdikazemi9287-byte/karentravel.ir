const assert=require('node:assert/strict');
const ts=require('/home/ubuntu/karenseir-current/node_modules/typescript');
const fs=require('node:fs'),vm=require('node:vm');
const source=ts.transpile(fs.readFileSync('/home/ubuntu/karenseir-current/lib/domain/jalali.ts','utf8'),{module:ts.ModuleKind.CommonJS});
const mod={exports:{}};vm.runInNewContext(source,{module:mod,exports:mod.exports});
const {jalaliToIso,isoToJalali,formatJalali,jalaliMonthLength}=mod.exports;
assert.equal(jalaliToIso({jy:1405,jm:6,jd:18}),'2026-09-09');
assert.equal(Object.values(isoToJalali('2026-09-09')).join(','),'1405,6,18');
assert.equal(formatJalali('2026-09-09'),'۱۸ شهریور ۱۴۰۵');
assert.equal(jalaliToIso({jy:1404,jm:1,jd:1}),'2025-03-21');
assert.equal(jalaliToIso({jy:1403,jm:12,jd:30}),'2025-03-20');
assert.equal(jalaliMonthLength(1403,12),30);
assert.equal(jalaliMonthLength(1404,12),29);
for(const iso of ['2025-03-21','2026-03-20','2026-03-21','2026-09-09','2027-03-20']){const d=isoToJalali(iso);assert.equal(jalaliToIso(d),iso)}
console.log('jalali conversion tests: PASS');
