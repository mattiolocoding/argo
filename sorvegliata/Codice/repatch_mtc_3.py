import paramiko, select, time, sys, json
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.55.200', username='neptune', password='Neptune2026!?')

def run_pty(cmd, password=None, timeout=25):
    transport = ssh.get_transport()
    chan = transport.open_session()
    chan.get_pty()
    chan.exec_command(cmd)
    output = b''
    pw_sent = False
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([chan], [], [], 1.0)
        if r:
            chunk = chan.recv(8192)
            if not chunk: break
            output += chunk
            if password and not pw_sent and b'[sudo]' in output:
                time.sleep(0.3)
                chan.send(password.encode() + b'\n')
                pw_sent = True
        if chan.exit_status_ready() and not chan.recv_ready(): break
    return output.decode('utf-8', errors='replace')

MK = '/var/lib/snapd/snap/bin/microk8s'
PW = 'Neptune2026!?'

def kubectl(cmd):
    out = run_pty(f'sudo {MK} kubectl -n neptune-dev {cmd} 2>&1', password=PW)
    return '\n'.join([l for l in out.split('\n') if '[sudo]' not in l and 'password' not in l.lower()])

# Get current config
raw = kubectl('get configmap mtc-config -o jsonpath="{.data.mtc\\.json}"')
cfg = json.loads(raw)
print(f'Current id_iff: {cfg["sensors"]["id_iff"]}')

# Change to 3
cfg['sensors']['id_iff'] = 3
new_json = json.dumps(cfg, separators=(',', ':'))

sftp = ssh.open_sftp()
with sftp.open('/tmp/mtc_new3.json', 'w') as f:
    f.write(new_json)
sftp.close()

out = run_pty(
    f'sudo {MK} kubectl -n neptune-dev create configmap mtc-config '
    f'--from-file=mtc.json=/tmp/mtc_new3.json '
    f'--dry-run=client -o yaml | sudo {MK} kubectl -n neptune-dev apply -f - 2>&1',
    password=PW, timeout=20
)
lines = [l for l in out.split('\n') if '[sudo]' not in l and 'password' not in l.lower()]
print('\n'.join(lines))

# Restart MTC
print('\n=== Restart MTC ===')
print(kubectl('rollout restart deployment/mtc'))
time.sleep(3)
print(kubectl('rollout status deployment/mtc --timeout=60s'))

# Get new pod
time.sleep(5)
out = kubectl('get pods | grep mtc-')
pods = [l.split()[0] for l in out.split('\n') if 'mtc-' in l and 'Running' in l]
pod = pods[0] if pods else None
print(f'New pod: {pod}')

if pod:
    # Verify config
    raw = kubectl(f'exec {pod} -- cat /mtc/mtc.json')
    cfg2 = json.loads('\n'.join([l for l in raw.split('\n') if l.strip()]))
    print(f'Verified id_iff = {cfg2["sensors"]["id_iff"]}')

    # Wait and check for IFF source tracks
    print('\nWaiting 20s for IFF tracks...')
    time.sleep(20)
    out = kubectl(f'logs {pod} --tail=60')
    lines = out.split('\n')
    iff_lines = [l for l in lines if 'source_id: 3' in l or 'source_id: 2' in l]
    print(f'IFF source tracks (source_id 2 or 3): {len(iff_lines)}')
    for l in iff_lines[:5]:
        print(f'  {l}')
    print(f'\nLast 5 lines:')
    for l in lines[-5:]:
        print(f'  {l}')

ssh.close()
