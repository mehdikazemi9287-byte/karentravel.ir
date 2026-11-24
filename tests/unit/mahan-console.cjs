// Staff Mahan console helpers (lib/mahan-console.ts). Run: node tests/unit/mahan-console.cjs
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const scope={exports:{},globalThis:{crypto:require('node:crypto')}};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('lib/mahan-console.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,scope);
const M=scope.exports;const plain=x=>JSON.parse(JSON.stringify(x));

// Persian / Arabic digits are converted, never stripped
assert.equal(M.latinDigits('۱۴۰۵-۰۸-۱۷ ٣'),'1405-08-17 3');
assert.equal(M.isoDate('۲۰۲۶/۱۲/۰۱'),'2026-12-01');assert.equal(M.isoDate('2026-2-30'),null);assert.equal(M.isoDate('01-12-2026'),null);
assert.equal(M.normalizePhone('۰۹۱۲ ۱۲۳-۴۵۶۷'),'09121234567');assert.ok(M.isPhone('۰۹۱۲۱۲۳۴۵۶۷'));assert.ok(!M.isPhone('0912'));

// search form → API body
const T='2026-11-24';const base={origin:'ika',destination:'bkk',depart_on:'۲۰۲۶-۱۲-۰۱',return_on:'',trip:'one_way',adults:'۲',children:'0',infants:'1'};
assert.deepEqual(plain(M.searchBody(base,T).body),{origin:'IKA',destination:'BKK',depart_on:'2026-12-01',adults:2,children:0,infants:1});
assert.ok(M.searchBody({...base,trip:'round_trip',return_on:'2026-11-30'},T).errors.length===1);
assert.equal(M.searchBody({...base,trip:'round_trip',return_on:'2026-12-05'},T).body.return_on,'2026-12-05');
assert.ok(M.searchBody({...base,depart_on:'2026-11-01'},T).errors.length);
assert.ok(M.searchBody({...base,infants:'3'},T).errors.length);
assert.ok(M.searchBody({...base,destination:'IKA'},T).errors.length);
assert.ok(M.searchBody({...base,origin:'تهران'},T).errors.length);
assert.equal(M.searchBody({...base,trip:'one_way',return_on:'garbage'},T).body.return_on,undefined);

// passengers
const ok={type:'ADT',first_name:' Testa ',last_name:'Fixture',gender:'F',birth_date:'۱۹۸۶-۰۱-۰۷',document_type:'P',document_number:'t۱۲۳۴۵۶۷',document_expiry:'2030-11-16',nationality:'irn'};
assert.deepEqual(plain(M.validatePassenger(ok,T,'2026-12-01').body),{type:'ADT',first_name:'Testa',last_name:'Fixture',gender:'F',birth_date:'1986-01-07',document_type:'P',document_number:'T1234567',document_expiry:'2030-11-16',nationality:'IRN'});
const errs=p=>Object.keys(M.validatePassenger({...ok,...p},T,'2026-12-01').errors);
assert.deepEqual(errs({first_name:'تستا'}),['first_name']);
assert.deepEqual(errs({gender:''}),['gender']);
assert.deepEqual(errs({document_expiry:'2026-11-30'}),['document_expiry']);       // expires before the flight
assert.deepEqual(errs({document_expiry:'2026-11-24'}),['document_expiry']);       // expired today
assert.deepEqual(errs({birth_date:'2030-01-01'}),['birth_date']);
assert.deepEqual(errs({type:'INF',birth_date:'2023-01-01'}),['birth_date']);      // 3 years old is not an infant
assert.deepEqual(errs({type:'INF',birth_date:'2025-06-01'}),[]);
assert.deepEqual(errs({type:'CHD',birth_date:'2018-06-01'}),[]);
assert.deepEqual(errs({type:'ADT',birth_date:'2018-06-01'}),['birth_date']);
assert.deepEqual(errs({document_type:'I',document_number:'۰۰۱۲۳۴۵۶۷۸'}),[]);
assert.deepEqual(errs({document_type:'I',document_number:'AB12345'}),['document_number']);
assert.deepEqual(plain(M.emptyPassengers({adults:2,children:1,infants:1}).map(p=>p.type)),['ADT','ADT','CHD','INF']);

// Idempotency-Key per attempt: fresh after a definite refusal, same key while the outcome is unknown, stop on a lost Book answer
assert.equal(M.afterHold({status:'held'}),'done');
assert.equal(M.afterHold({status:'unknown'}),'stop');
assert.equal(M.afterHold({status:'price_changed'}),'new');
assert.equal(M.afterHold({status:'not_held'}),'new');
for(const [s,c] of [[409,'PRICE_CHANGED'],[409,'BOOK_REFUSED'],[409,'OFFER_EXPIRED'],[422,undefined],[403,undefined]])assert.equal(M.afterHold({httpStatus:s,code:c}),'new',`${s} ${c}`);
for(const [s,c] of [[0,undefined],[502,'MAHAN_PROVIDER_ERROR'],[504,undefined],[409,'HOLD_IN_PROGRESS'],[409,'IDEMPOTENCY_MISMATCH'],[401,undefined]])assert.equal(M.afterHold({httpStatus:s,code:c}),'reuse',`${s} ${c}`);
const k1=M.newHoldKey(),k2=M.newHoldKey();assert.ok(k1!==k2&&/^mahan-hold-/.test(k1)&&k1.length>=8&&k1.length<=120);

// API error details
assert.equal(M.apiProblem({code:'PRICE_CHANGED',message:'x'},'f').code,'PRICE_CHANGED');
assert.equal(M.apiProblem('کلید تکرار برای درخواست دیگری استفاده شده است','f').code,'IDEMPOTENCY_MISMATCH');
assert.ok(M.apiProblem([{loc:['body']}],'f').message.includes('فیلد'));
console.log('mahan-console: PASS');
