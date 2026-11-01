"""TEST-ONLY file-based project staging and Agent resource verification."""
import hashlib
import json
import os
import pathlib
import shutil
import time
from datetime import datetime, timezone
from validate import validate

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAME = 'DeploymentSmokeTest'
SRC = ROOT / 'ignition-project' / NAME

def fingerprint(p):
    return {
        x.relative_to(p).as_posix(): hashlib.sha256(x.read_bytes()).hexdigest()
        for x in p.rglob('*')
        if x.is_file() and x.name != '.lab-release.json' and '.git' not in x.parts
    }

def envdir(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError('Missing ' + name)
    p = pathlib.Path(value).resolve()
    if not p.is_dir():
        raise RuntimeError('Not an existing directory: ' + str(p))
    return p

def main():
    if os.getenv('IGNITION_LAB_ONLY') != 'YES':
        raise RuntimeError('LAB ONLY GATE')
    validate(SRC)
    sha = os.environ['RELEASE_SHA']
    if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
        raise RuntimeError('Invalid SHA')
    ctrl = envdir('CONTROLLER_PROJECTS_DIR')
    agent = envdir('AGENT_PROJECTS_DIR')
    triggers = envdir('CONTROLLER_TRIGGER_DIR')
    backups = envdir('DEPLOY_BACKUP_DIR')
    target, observed = ctrl / NAME, agent / NAME
    if target.resolve() == observed.resolve():
        raise RuntimeError('Controller and Agent same directory')
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_run = backups / (ts + '-' + sha[:10])
    backup_run.mkdir(parents=True, exist_ok=False)
    if target.exists():
        shutil.copytree(target, backup_run / 'controller_previous')
    if observed.exists():
        shutil.copytree(observed, backup_run / 'agent_previous')
    hashes = fingerprint(SRC)
    stage = ctrl / (NAME + '.staging-' + sha[:10])
    old = ctrl / (NAME + '.previous-' + sha[:10])
    if stage.exists() or old.exists():
        raise RuntimeError('Existing staging/previous path: stop')
    shutil.copytree(SRC, stage)
    if target.exists():
        target.rename(old)
    stage.rename(target)
    # CRITICAL: runtime scan + verification is not implemented yet.
    # EAM may send OLD runtime project even after filesystem replacement.
    trigger = {'sha': sha, 'project': NAME, 'task': 'Lab_Send_Project', 'created_at': ts}
    req = triggers / 'eam_request.json'
    tmp = triggers / ('eam_request.' + sha[:10] + '.tmp')
    if req.exists():
        raise RuntimeError('Pending EAM request exists: stop')
    tmp.write_text(json.dumps(trigger))
    tmp.replace(req)
    print('STAGED', sha, 'WAITING_FOR_EAM')
    evidence = {'sha': sha, 'stage': 'WAITING', 'backup': str(backup_run)}
    (ROOT / 'evidence').mkdir(exist_ok=True)
    deadline = time.monotonic() + 180
    receipt = triggers / ('started-' + sha + '.json')
    while time.monotonic() < deadline:
        if receipt.exists():
            break
        time.sleep(2)
    else:
        raise RuntimeError('EAM task not started: no receipt')
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if observed.is_dir():
            bad = [
                k for k, h in hashes.items()
                if not (observed / k).is_file()
                or hashlib.sha256((observed / k).read_bytes()).hexdigest() != h
            ]
            if not bad:
                evidence['stage'] = 'PASS_RESOURCE_TRANSFER'
                evidence['verified_files'] = len(hashes)
                (ROOT / 'evidence' / 'deployment.json').write_text(json.dumps(evidence, indent=2))
                print('PASS_RESOURCE_TRANSFER', sha, len(hashes))
                return
        time.sleep(3)
    evidence['stage'] = 'FAIL_AGENT_NOT_MATCHED'
    (ROOT / 'evidence' / 'deployment.json').write_text(json.dumps(evidence, indent=2))
    raise RuntimeError('EAM Agent not verified against source')
if __name__ == '__main__':
    main()
