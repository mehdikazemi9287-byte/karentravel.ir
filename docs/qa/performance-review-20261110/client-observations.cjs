const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const assert=require('node:assert/strict');
const repo=path.resolve(process.argv[2]||'karentravel.ir');
const source=fs.readFileSync(path.join(repo,'lib/api/karenseir-client.ts'),'utf8');
const output=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const mod={exports:{}};new Function('module','exports','require',output)(mod,mod.exports,require);
const {KarenSeirApi}=mod.exports;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 let calls=0,hasSignal=false;
 global.fetch=async(url,init)=>{calls++;hasSignal=Boolean(init.signal);await pause(5);return new Response('{}');};
 const api=new KarenSeirApi('https://isolated.invalid');
 await Promise.all([api.publicGet('/same'),api.publicGet('/same')]);
 const duplicate={concurrent_identical_reads:2,network_calls:calls,abort_signal_supplied:hasSignal};
 assert.equal(calls,2);assert.equal(hasSignal,false);
 let refreshCalls=0;const refreshTokens=[];
 api.setSession({access_token:'expired-test',refresh_token:'refresh-test',token_type:'bearer'});
 global.fetch=async(url,init)=>{
   if(url.endsWith('/auth/refresh')) {refreshCalls++;refreshTokens.push(JSON.parse(init.body).refresh_token);await pause(5);return new Response(JSON.stringify({access_token:'new-test',refresh_token:'rotated-test',token_type:'bearer'}));}
   if(init.headers.get('Authorization')==='Bearer expired-test'){await pause(1);return new Response('{}',{status:401});}
   return new Response('{}');
 };
 await Promise.all([api.get('/a'),api.get('/b')]);
 assert.equal(refreshCalls,2);assert.equal(new Set(refreshTokens).size,1);
 console.log(JSON.stringify({fixture:'isolated mocked fetch, no network or real credentials',duplicate,refresh:{concurrent_401:2,refresh_calls:refreshCalls,same_refresh_token_used_twice:true}},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
