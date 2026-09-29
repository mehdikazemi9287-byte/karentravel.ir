import copy,importlib.util,json,subprocess,sys
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('promote','/home/ubuntu/karenseir-current/deploy/promote_worker_reaper_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
manifest=json.loads(Path('/home/ubuntu/karenseir-current/docs/recovery/evidence/worker-reaper-guard/candidate.json').read_text())
with patch.object(sys,'argv',['promote']),patch.object(m.subprocess,'check_output') as call:
 try:m.main();raise AssertionError('approval guard missing')
 except SystemExit as error:assert error.code==2
 assert not call.called

def exercise(failure):
 name=manifest['target'];old={'Image':manifest['expected_old_image'],'Config':{'Env':[],'Healthcheck':{'Test':['CMD-SHELL','true']},'Cmd':['python','-m','app.outbox_worker']},'HostConfig':{'Privileged':False,'RestartPolicy':{'Name':'unless-stopped'}},'Mounts':[],'NetworkSettings':{'Networks':{'qa':{}}},'State':{'Running':True,'Health':{'Status':'healthy'}},'RestartCount':0}
 containers={name:copy.deepcopy(old)}
 for n in ('karenseir-api-1','karenseir-frontend-1','karenseir-search'):containers[n]=copy.deepcopy(old)
 before=copy.deepcopy(containers);hit=[False]
 def fake_run(*a):
  if a[:3]==('docker','image','inspect'):return manifest['image_id']
  if a[:2]==('docker','run'):
   return json.dumps({'git_commit':manifest['commit']}) if '/app/build_info.json' in a else manifest['worker_sha256']+'  /app/app/outbox_worker.py'
  if a[:2]==('docker','create'):
   n=a[a.index('--name')+1];containers[n]=copy.deepcopy(old);containers[n]['Image']=manifest['image_id'];return 'qa-created'
  if a[:2]==('docker','stop'):containers[a[2]]['State']['Running']=False;return ''
  if a[:2]==('docker','rename'):
   if failure=='rename' and a[2]==name and a[3]==manifest['rollback']:hit[0]=True;raise RuntimeError('injected rename failure')
   containers[a[3]]=containers.pop(a[2]);return ''
  if a[:2]==('docker','start'):containers[a[2]]['State']['Running']=True;return ''
  if a[:2]==('docker','exec'):hit[0]=True;return json.dumps({'reservation_reaper':'enabled'}) # force health contract failure
  raise AssertionError(a)
 def command(a,**kw):
  if a[:2]==['docker','inspect']:return subprocess.CompletedProcess(a,0 if a[2] in containers else 1)
  if a[:2]==['docker','stop']:fake_run(*a);return subprocess.CompletedProcess(a,0)
  raise AssertionError(a)
 with patch.object(sys,'argv',['promote','--approved']),patch.object(m,'run',side_effect=fake_run),patch.object(m,'inspect',side_effect=lambda n:copy.deepcopy(containers[n])),patch.object(m.subprocess,'run',side_effect=command),patch.object(m.time,'sleep'):
  try:m.main();raise AssertionError('injected failure not detected')
  except (AssertionError,RuntimeError):pass
 assert hit[0], 'Failure injection was not reached'
 assert containers[name]['Image']==manifest['expected_old_image'] and containers[name]['State']['Running']
 assert all(containers[n]==before[n] for n in ('karenseir-api-1','karenseir-frontend-1','karenseir-search'))
exercise('health');exercise('rename')
print('PASS: approval guard; injected health failure rollback; rename failure recovery; no actual Docker mutation')
