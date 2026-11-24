// Offline sales request outcome (lib/trip-request.ts, Launch V1 item 7). Run: node tests/unit/trip-request.cjs
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const src=ts.transpileModule(fs.readFileSync('lib/trip-request.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const scope={exports:{},require};scope.module={exports:scope.exports};vm.runInNewContext(src,scope);const T=scope.exports;
const kind=r=>T.requestOutcome(r).kind;
// success only for a 2xx answer that says {received: true}
assert.equal(kind({status:200,body:{received:true}}),'done');assert.equal(kind({status:202,body:{received:true}}),'done');
for(const body of [undefined,null,{},{received:false},{received:'true'},'ok'])assert.equal(kind({status:200,body}),'error',JSON.stringify(body));
// 503 = intake not configured (no SALES_DESK_PUBLIC_TENANT / consumer tenant): a clear «not active», never a success
assert.equal(kind({status:503}),'inactive');assert.match(T.INACTIVE_TITLE,/فعال نشده/);assert.match(T.INACTIVE_TEXT,/ثبت نشد/);
// other failures are errors with a Persian message, never 'done'
for(const status of [0,400,401,403,404,422,429,500,502])assert.equal(kind({status}),'error',String(status));
assert.match(T.requestOutcome({status:422}).message,/موبایل/);assert.match(T.requestOutcome({status:429}).message,/کمی بعد/);
console.log('trip-request: PASS');
