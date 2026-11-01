"""Opt-in lab automation: backup -> stage/update -> scan -> EAM request -> Agent file verification.

Requires separately installed Controller Gateway timer from controller/eam_trigger_gateway_timer.py.
Never claims E2E/Perspective PASS from file hashes alone.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import ssl

ROOT = Path(__file__).resolve().parents[1]
DATA = "/usr/local/bin/ignition/data"
PROJECT = "DeploymentSmokeTest"
CTRL = "ignition-eam-controller"
AGENT = "ignition-eam-agent"
TASK = "CICD-AUTO-DeploymentSmokeTest"
REQUESTS = DATA + "/eam-requests"
EVIDENCE = ROOT / "evidence" / "auto-eam.json"

def cmd(*args, **kw):
    return subprocess.run(args, check=True, stderr=subprocess.PIPE, **kw)

def docker(*args):
    return cmd("docker", *args)

def hashes(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}

def remote_hashes(container):
    path = DATA + "/projects/" + PROJECT
    return {rel: subprocess.check_output(["docker","exec",container,"sha256sum",path+"/"+rel],
                                          text=True).split()[0] for rel in SOURCE_HASHES}

def verify_container(name):
    value = subprocess.check_output(["docker","inspect","--format","{{.State.Running}}",name],text=True).strip()
    if value != "true":
        raise RuntimeError("Container not running: "+name)

def api_scan():
    # Confirm method/permissions at Gateway /openapi for this exact installed version.
    token = os.getenv("IGNITION_GATEWAY_API_TOKEN")
    if not token:
        raise RuntimeError("Missing IGNITION_GATEWAY_API_TOKEN")
    ca = Path(os.environ.get("IGNITION_CONTROLLER_CA_FILE", str(Path.home() / "ignition-eam-lab/certs/lab-root-ca.crt")))
    if not ca.is_file():
        raise RuntimeError("Trusted Controller CA missing")
    context = ssl.create_default_context(cafile=str(ca))
    req = Request("https://localhost:9143/data/api/v1/scan/projects",
                  data=b"", method="POST",
                  headers={"X-Ignition-API-Token":token})
    with urlopen(req,timeout=30,context=context) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError("Gateway project scan rejected")
    # HTTP 2xx confirms scan accepted, NOT that Ignition loaded this release.
    # No EAM task may run until independent runtime evidence is supplied.

def main():
    if os.environ.get("IGNITION_LAB_ONLY") != "YES":
        raise RuntimeError("Lab permission gate")
    if os.environ.get("IGNITION_CONTROLLER_CONTAINER") != CTRL or os.environ.get("IGNITION_AGENT_CONTAINER") != AGENT:
        raise RuntimeError("Container allowlist mismatch")
    sha=os.environ.get("RELEASE_SHA","")
    if not re.fullmatch(r"[0-9a-f]{40}",sha):
        raise RuntimeError("Invalid commit sha")
    manifest=json.loads((ROOT/"manifests/ignition-test.json").read_text())
    if manifest.get("project")!=PROJECT or manifest.get("target_agent")!="EAM-Agent" or manifest.get("eam_task")!=TASK or manifest.get("production_approved") is not False:
        raise RuntimeError("Manifest not authorized")
    if manifest.get("automatic_eam_enabled") is not True:
        raise RuntimeError("HOLD: manifest auto EAM switch is not enabled")
    if not manifest.get("requires_gateway_scan") or not manifest.get("requires_runtime_smoke"):
        raise RuntimeError("Verification gates disabled")
    src=ROOT/"ignition-project"/PROJECT
    if not (src/"project.json").is_file() or any(p.is_symlink() for p in src.rglob("*")):
        raise RuntimeError("Invalid project files")
    global SOURCE_HASHES
    SOURCE_HASHES=hashes(src)
    verify_container(CTRL)
    verify_container(AGENT)
    backup_base=Path(os.environ.get("IGNITION_BACKUP_DIR","")).expanduser().resolve()
    if not backup_base.is_dir() or backup_base==ROOT or ROOT in backup_base.parents:
        raise RuntimeError("Backup dir missing/unsafe")
    backup=backup_base/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+sha[:12]+"-auto")
    backup.mkdir(mode=0o700)
    report={"sha":sha,"project":PROJECT,"backup":str(backup),"stage":"STARTED","e2e":"HOLD"}
    EVIDENCE.parent.mkdir(exist_ok=True)
    try:
        # Back up BOTH gateways' project trees prior to modifying Controller.
        for name in (CTRL,AGENT):
            with (backup/(name+".tar")).open("wb") as out:
                docker("exec",name,"tar","-cf","-","-C",DATA,"projects",stdout=out)
            cmd("tar","-tf",str(backup/(name+".tar")),stdout=subprocess.DEVNULL)
        report["backup_verified"]=True
        # No trigger may already be outstanding.
        docker("exec",CTRL,"mkdir","-p",REQUESTS)
        for marker in ("eam_request.json","eam_request.processing"):
            found=subprocess.run(["docker","exec",CTRL,"test","-e",REQUESTS+"/"+marker])
            if found.returncode != 1:
                raise RuntimeError("Existing or inaccessible EAM trigger: "+marker)
        # Stage to temporary name and swap only after backups; lab-specific.
        dst=DATA+"/projects/"+PROJECT
        tmp=DATA+"/projects/.ci-stage-"+sha[:12]
        existing=subprocess.run(["docker","exec",CTRL,"test","-e",tmp])
        if existing.returncode != 1:
            raise RuntimeError("Existing staging path")
        docker("cp",str(src),CTRL+":"+tmp)
        docker("exec","-u","0",CTRL,"chown","-R","ignition:ignition",tmp)
        # Verify hashes before replacing.
        for rel, expected in SOURCE_HASHES.items():
            got=subprocess.check_output(["docker","exec",CTRL,"sha256sum",tmp+"/"+rel],text=True).split()[0]
            if got!=expected:
                raise RuntimeError("Staging hash mismatch "+rel)
        # Stop if existing project has files not represented in Git (no silent loss).
        if subprocess.run(["docker","exec",CTRL,"test","-e",dst]).returncode==0:
            existing_files=subprocess.check_output(["docker","exec",CTRL,"find",dst,"-type","f","-printf","%P\\n"],text=True).splitlines()
            extra=set(existing_files)-set(SOURCE_HASHES)
            if extra:
                raise RuntimeError("Controller contains unmanaged resources: "+", ".join(sorted(extra)[:5]))
            prior=DATA+"/projects/.ci-prior-"+sha[:12]
            if subprocess.run(["docker","exec",CTRL,"test","-e",prior]).returncode!=1:
                raise RuntimeError("Prior directory already exists")
            docker("exec",CTRL,"mv",dst,prior)
        docker("exec",CTRL,"mv",tmp,dst)
        if remote_hashes(CTRL)!=SOURCE_HASHES:
            raise RuntimeError("Controller project hash mismatch")
        report["stage"]="CONTROLLER_FILES_VERIFIED"
        api_scan()
        report["gateway_scan"]="API_ACCEPTED"
        # Trigger must be installed in an isolated Controller-only project.
        # Scan accepted does not prove runtime SHA. Explicit runtime proof is required.
        if os.environ.get("IGNITION_CONTROLLER_RUNTIME_VERIFIED_SHA") != sha:
            raise RuntimeError("HOLD: Controller runtime SHA not attested. Cannot invoke EAM.")
        report["controller_runtime"]="OPERATOR_ATTESTED"
        request={"sha":sha,"project":PROJECT,"task":TASK}
        with __import__("tempfile").NamedTemporaryFile(mode="w",suffix=".json",delete=False) as f:
            json.dump(request,f)
            local=f.name
        try:
            docker("cp",local,CTRL+":"+REQUESTS+"/eam_request.json")
        finally:
            Path(local).unlink(missing_ok=True)
        receipt=REQUESTS+"/started-"+sha+".json"
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if subprocess.run(["docker","exec",CTRL,"test","-f",receipt],stdout=subprocess.DEVNULL).returncode==0:
                result=json.loads(subprocess.check_output(["docker","exec",CTRL,"cat",receipt],text=True))
                if result.get("sha")!=sha or result.get("task_invoked") is not True:
                    raise RuntimeError("Invalid EAM receipt")
                report["eam_trigger"]="INVOKED_NOT_TASK_COMPLETED"
                break
            time.sleep(2)
        else:
            raise RuntimeError("EAM trigger receipt absent")
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            if subprocess.run(["docker","exec",AGENT,"test","-d",DATA+"/projects/"+PROJECT],
                              stdout=subprocess.DEVNULL).returncode==0:
                try:
                    if remote_hashes(AGENT)==SOURCE_HASHES:
                        report["agent_files"]="MATCH"
                        report["stage"]="RESOURCE_TRANSFER_VERIFIED"
                        return
                except subprocess.CalledProcessError:
                    pass
            time.sleep(3)
        raise RuntimeError("Agent resources did not match release")
    except Exception as exc:
        report["error"]=str(exc)
        report["stage"]="FAILED_OR_HOLD"
        raise
    finally:
        EVIDENCE.write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":
    main()
