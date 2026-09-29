"""Worker-only promotion. Execute ONLY after explicit production approval.
No migration, privilege change, reaper activation, or API/web replacement.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def inspect(name):
    return json.loads(run('docker', 'inspect', name))[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approved', action='store_true', help='Operator confirms explicit approval already received')
    parser.add_argument('--check-only', action='store_true', help='Verify fingerprints/settings without staging or modifying Production')
    args = parser.parse_args()
    if not args.approved and not args.check_only:
        parser.error('Explicit production approval is required before execution')
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'docs/recovery/evidence/worker-reaper-guard/candidate.json').read_text())
    name, image, backup = manifest['target'], manifest['image'], manifest['rollback']
    old = inspect(name)
    assert old['Image'] == manifest['expected_old_image'], 'Worker fingerprint changed; stop'
    before = {n: inspect(n)['Image'] for n in ('karenseir-api-1', 'karenseir-frontend-1', 'karenseir-search')}
    assert before['karenseir-api-1'] == manifest['expected_old_image'], 'API baseline changed; stop'
    assert run('docker', 'image', 'inspect', image, '--format', '{{.Id}}') == manifest['image_id']
    metadata = json.loads(run('docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'cat', image, '/app/build_info.json'))
    assert metadata['git_commit'] == manifest['commit']
    assert run('docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'sha256sum', image, '/app/app/outbox_worker.py').split()[0] == manifest['worker_sha256']
    env = dict(v.split('=', 1) for v in old['Config']['Env'])
    for channel in ('SMS', 'PUSH'):
        assert env.get(channel + '_PROVIDER_MODE', env.get('NOTIFICATION_PROVIDER_MODE', 'disabled')) == 'disabled', 'External channel mode changed; stop'
    env['RESERVATION_REAPER_ENABLED'] = '0'
    assert all('\n' not in v and '\r' not in v for v in env.values()), 'Unsupported multiline environment; stop'
    host = old['HostConfig']
    assert not host['Privileged'] and not host.get('CapAdd') and not host.get('CapDrop') and not host.get('SecurityOpt')
    assert not host.get('ReadonlyRootfs') and not host.get('Memory') and not host.get('NanoCpus')
    assert len(old['NetworkSettings']['Networks']) == 1
    network = next(iter(old['NetworkSettings']['Networks']))
    staged = name + '-reaper-guard-ready'
    for candidate in (backup, staged, name + '-reaper-guard-failed'):
        assert subprocess.run(['docker', 'inspect', candidate], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0, 'Recovery/staging name already exists; stop'
    if args.check_only:
        print('CHECK_ONLY_PASS: candidate identity, current fingerprints and guarded settings; no Production mutation')
        return
    fd, env_path = tempfile.mkstemp(prefix='karen-worker-guard-', suffix='.env')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write('\n'.join(k + '=' + v for k, v in env.items()) + '\n')
        command = ['docker', 'create', '--name', staged, '--network', network, '--network-alias', 'worker', '--restart', host['RestartPolicy']['Name'], '--env-file', env_path]
        if host.get('LogConfig', {}).get('Type'):
            command += ['--log-driver', host['LogConfig']['Type']]
            for key, value in host['LogConfig'].get('Config', {}).items():
                command += ['--log-opt', key + '=' + value]
        for mount in old['Mounts']:
            assert mount['Type'] == 'volume'
            command += ['-v', mount['Name'] + ':' + mount['Destination'] + ('' if mount['RW'] else ':ro')]
        for port, bindings in (host.get('PortBindings') or {}).items():
            for binding in bindings:
                command += ['-p', (binding['HostIp'] + ':' if binding['HostIp'] else '') + binding['HostPort'] + ':' + port]
        for key, value in (old['Config'].get('Labels') or {}).items():
            command += ['--label', key + '=' + value]
        command += ['--label', 'io.karentravel.source-commit=' + manifest['commit']]
        if old['Config'].get('User'):
            command += ['--user', old['Config']['User']]
        if old['Config'].get('WorkingDir'):
            command += ['--workdir', old['Config']['WorkingDir']]
        check = old['Config']['Healthcheck']['Test']
        health_cmd = check[1] if check[0] == 'CMD-SHELL' else shlex.join(check[1:])
        command += ['--health-cmd', health_cmd, '--health-interval', '5s', '--health-timeout', '5s', '--health-retries', '3']
        run(*command, image, *old['Config']['Cmd'])
    finally:
        os.unlink(env_path)
    promoted = False
    try:
        run('docker', 'stop', name)
        run('docker', 'rename', name, backup)
        promoted = True
        run('docker', 'rename', staged, name)
        run('docker', 'start', name)
        for _ in range(45):
            state = inspect(name)['State']
            if state.get('Health', {}).get('Status') == 'healthy':
                break
            if not state['Running']:
                raise RuntimeError('Worker stopped during health verification')
            time.sleep(1)
        else:
            raise RuntimeError('Worker health timeout')
        health = json.loads(run('docker', 'exec', name, 'python', '-c', 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:9101/health").read().decode())'))
        assert health['reservation_reaper'] == 'disabled'
        # Longer than the previous twelve idle ticks (180 seconds).
        for _ in range(7):
            time.sleep(30)
            current = inspect(name)
            assert current['RestartCount'] == 0 and current['State']['Health']['Status'] == 'healthy'
        assert {n: inspect(n)['Image'] for n in before} == before
        print(json.dumps({'worker_commit': manifest['commit'], 'health': health, 'observation_seconds': 210, 'restarts': 0, 'rollback': backup, 'api_web_search_unchanged': True, 'migration': False}))
    except BaseException:
        if promoted:
            subprocess.run(['docker', 'stop', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if subprocess.run(['docker', 'inspect', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                run('docker', 'rename', name, name + '-reaper-guard-failed')
            run('docker', 'rename', backup, name)
            run('docker', 'start', name)
        elif subprocess.run(['docker', 'inspect', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 and inspect(name)['Image'] == manifest['expected_old_image']:
            run('docker', 'start', name)
        raise


if __name__ == '__main__':
    main()
