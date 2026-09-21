import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
repo = Path(sys.argv[1]).resolve()
python = Path(sys.argv[2]).absolute()
base = '6f998577d547b1e54ec662dac63583aa11e3b84b'
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
if head != base:
    paths = subprocess.check_output(['git', 'diff', '--name-only', base, head], cwd=repo, text=True).splitlines()
    if paths != ['docs/docs/gpt-researcher/retrievers/mcp-configs.mdx']:
        raise SystemExit(f'Expected source {base}; only the companion documentation change may differ')
subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'gpt_researcher', 'tests'], cwd=repo, check=True)
label = sys.argv[3] if len(sys.argv) > 3 else 'host-validation'
if Path(label).name != label:
    raise SystemExit('The log label must be a simple file name')
command = [str(python), '-m', 'pytest', str(root/'test_remote_mcp.py'),
           'tests/test_mcp_client_config.py', 'tests/test_mcp_client_non_dict_config.py',
           '-q', '--timeout=45']
env = {'PATH':'/usr/bin:/bin:/opt/homebrew/bin', 'PYTHONDONTWRITEBYTECODE':'1', 'GPTR_BLOCK_NETWORK':'1'}
with (root/f'{label}.log').open('w') as log:
    result = subprocess.run(command,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
(root/f'{label}.json').write_text(json.dumps({'sampled_at':datetime.now(timezone.utc).isoformat(),
    'command':command,'cwd':str(repo),'exit_code':result.returncode,
    'environment':'Explicit allowlist; no inherited credentials; loopback network only'},indent=2)+'\n')
print((root/f'{label}.log').read_text()[-7000:])
sys.exit(result.returncode)
