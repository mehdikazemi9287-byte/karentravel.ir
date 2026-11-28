// «امروز» for the flight date strip is the Tehran date, not UTC. Run: node tests/unit/tehran-today.cjs
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync('lib/tehran-today.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const scope={exports:{},Date,Intl};vm.runInNewContext(code,scope);const f=scope.exports.tehranToday;
assert.equal(f(new Date('2026-11-27T21:00:00Z')),'2026-11-28');   // 00:30 Tehran, UTC still the 27th
assert.equal(f(new Date('2026-11-27T20:29:00Z')),'2026-11-27');   // 23:59 Tehran
assert.equal(f(new Date('2026-11-28T10:00:00Z')),'2026-11-28');
assert.match(f(),/^\d{4}-\d{2}-\d{2}$/);
console.log('PASS tehran-today: Tehran calendar date, never the UTC date');
