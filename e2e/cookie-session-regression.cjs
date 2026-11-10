// M-3 cookie mode: no token in JS storage, no Authorization header, CSRF header on state-changing calls,
// cookie refresh sends no refresh_token, logout sends CSRF and an empty body. Bearer mode unchanged (see session-refresh-regression).
const fs=require('fs'),ts=require('typescript'),Module=require('module'),assert=require('assert');
const source=process.argv[2]||require('path').resolve(__dirname,'../lib/api/karenseir-client.ts');const compiled=ts.transpileModule(fs.readFileSync(source,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;const mod=new Module(source);mod._compile(compiled,source);const {KarenSeirApi}=mod.exports;
global.document={cookie:'other=1; karenseir_csrf=csrf-value'};
const calls=[];let expired=true;
global.fetch=async(url,init)=>{const h=init.headers instanceof Headers?init.headers:new Headers(init.headers);calls.push({url,method:init.method||'GET',auth:h.get('Authorization'),csrf:h.get('X-CSRF-Token'),body:init.body,credentials:init.credentials});
  if(url.endsWith('/auth/dev-login'))return new Response(JSON.stringify({token_type:'cookie',subject:{iss:'karenseir-api',sub:'7',tenant:1},user:{name:'n',role:'employee',tenant:'t'}}),{status:200});
  if(url.endsWith('/auth/refresh')){expired=false;return new Response(JSON.stringify({token_type:'cookie',subject:{iss:'karenseir-api',sub:'7',tenant:1}}),{status:200})}
  if(url.endsWith('/auth/logout'))return new Response(null,{status:204});
  if(url.endsWith('/private')&&expired)return new Response('{}',{status:401});
  return new Response(JSON.stringify({ok:true}),{status:200})};
(async()=>{const api=new KarenSeirApi('http://isolated.invalid');const s=await api.devLogin('e@x.test');
  assert.equal(s.token_type,'cookie');assert(s.access_token.startsWith('cookie.')&&s.access_token.endsWith('.'),'only an unsigned placeholder is kept in JS');assert.equal(s.refresh_token,'cookie');
  const claims=JSON.parse(Buffer.from(s.access_token.split('.')[1],'base64').toString());assert.equal(claims.sub,'7');assert.equal(claims.iss,'karenseir-api');
  assert((await api.get('/private')).ok);const g=calls.filter(c=>c.url.endsWith('/private'));assert(g.every(c=>c.auth===null&&c.csrf===null&&c.credentials==='same-origin'),'GET: cookie only, no header');
  const r=calls.find(c=>c.url.endsWith('/auth/refresh'));assert.equal(r.csrf,'csrf-value');assert(!JSON.parse(r.body).refresh_token,'cookie refresh sends no token');
  await api.post('/write',{a:1});const w=calls.find(c=>c.url.endsWith('/write'));assert.equal(w.auth,null);assert.equal(w.csrf,'csrf-value');
  await api.logout();const l=calls.find(c=>c.url.endsWith('/auth/logout'));assert.equal(l.csrf,'csrf-value');assert.equal(l.auth,null);assert.equal(l.body,'{}');
  console.log('PASS: cookie session keeps no token in JS, sends CSRF on writes/refresh/logout')})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
