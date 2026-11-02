"""TEST-only Factory A: create a unique native project on local EAM Controller."""
import argparse
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tarfile
import time
import uuid
from urllib.request import Request, urlopen
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import plan_release, validate_catalog
from scripts.verify_stage_approval import verify as verify_github_approval
CTRL = "ignition-eam-controller"
AGENT = "ignition-eam-agent"
PROJECT = "FactoryASmoke"
DATA = "/usr/local/bin/ignition/data"
URL = "https://localhost:9143/data/api/v1/scan/projects"
REPORT = ROOT / "evidence/factory-a-controller-smoke.json"

def must(condition, reason):
    if not condition:
        raise RuntimeError("HOLD: " + reason)

def run(*args, stdout=None):
    return subprocess.run(args, check=True, stdout=stdout, stderr=subprocess.PIPE)

def out(*args):
    return subprocess.check_output(args, stderr=subprocess.PIPE, text=True).strip()

def present(path):
    p = subprocess.run(["docker","exec",CTRL,"test","-e",path],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    must(p.returncode in (0,1), "cannot inspect Controller")
    return p.returncode == 0

def verify_hashes(base, expected):
    for name, checksum in expected.items():
        received = out("docker","exec",CTRL,"sha256sum",base+"/"+name).split()[0]
        must(received == checksum, "content mismatch " + name)

def scan(token, ctx):
    headers = {"X-Ignition-API-Token":token}
    with urlopen(Request(URL,data=b"",method="POST",headers=headers),
                 context=ctx,timeout=30) as response:
        must(response.status == 200, "Controller scan HTTP error")
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        with urlopen(Request(URL,headers=headers),context=ctx,timeout=30) as response:
            state=json.load(response)
        if state.get("scanActive") is False:
            return
        time.sleep(2)
    raise RuntimeError("HOLD: Controller scan did not become idle")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sha",required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-only",action="store_true")
    group.add_argument("--stage-controller",action="store_true")
    a=p.parse_args()
    must(bool(re.fullmatch("[0-9a-f]{40}",a.sha)), "invalid release commit")
    validate_catalog(ROOT/"factories")
    plan=plan_release(ROOT/"factories","lab-warehouse","warehouse-main","test",a.sha)
    projects=[project for project in plan["projects"] if project["name"]==PROJECT]
    must(len(projects)==1,"smoke project not in factory manifest")
    expected=projects[0]["sha256"]
    evidence={"sha":a.sha,"project":PROJECT,"mode":"TEST_CONTROLLER_ONLY",
              "status":"VALIDATED_NOT_DEPLOYED" if a.validate_only else "HOLD",
              "eam_send_project":"NOT_RUN","agent_verification":"NOT_RUN",
              "browser_render":"NOT_TESTED","fat":"NOT_TESTED"}
    if a.validate_only:
        print(json.dumps(evidence,indent=2))
        return
    must(os.getenv("FACTORY_A_SMOKE_CONFIRM")=="YES","explicit LAB gate")
    must(os.getenv("GITHUB_REPOSITORY")=="tomha85/ignition-cicd","repository gate")
    must(os.getenv("GITHUB_REF") in ("refs/heads/main","refs/heads/feat/reusable-multifactory-framework-v1"),"branch gate")
    must(os.getenv("GITHUB_EVENT_NAME") in ("push", "workflow_dispatch"),
         "only explicit workflow dispatch or existing LAB smoke push allowed")
    must(os.getenv("GITHUB_SHA")==a.sha,"release SHA gate")
    must(out("git", "rev-parse", "HEAD")==a.sha,
         "checkout must be the exact reviewed release commit")
    # Even if someone misconfigures the GitHub Environment, Controller writes
    # require a real required-reviewer approval for this exact run and branch.
    approval = verify_github_approval(os.environ, os.getenv("GH_APPROVAL_READ_TOKEN"))
    evidence["github_stage_approval"] = approval["status"]
    must(os.getenv("IGNITION_CONTROLLER_CONTAINER")==CTRL,"Controller allowlist")
    must(os.getenv("IGNITION_AGENT_CONTAINER")==AGENT,"Agent allowlist")
    backup_path=os.getenv("IGNITION_BACKUP_DIR")
    must(bool(backup_path),"backup root missing")
    backup_root=Path(backup_path).expanduser().resolve()
    must(backup_root.is_dir() and backup_root!=ROOT and ROOT not in backup_root.parents,"unsafe backup root")
    ca=Path(os.getenv("IGNITION_CONTROLLER_CA_FILE") or "/invalid")
    token=os.getenv("IGNITION_CONTROLLER_API_TOKEN")
    must(bool(token) and ca.is_file(),"Controller HTTPS token/CA required")
    ctx=ssl.create_default_context(cafile=str(ca))
    for container in (CTRL,AGENT):
        must(out("docker","inspect","--format","{{.State.Running}}",container)=="true",
             "LAB container not running: "+container)
    stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+uuid.uuid4().hex[:8]
    backup=backup_root/("framework-factory-a-"+stamp)
    backup.mkdir(mode=0o700)
    evidence["backup"]=str(backup)
    dst=DATA+"/projects/"+PROJECT
    staged=DATA+"/.framework-stage-"+stamp
    rejected=DATA+"/.framework-rejected-"+stamp
    created=False
    replaced=False
    prior=DATA+"/.framework-prior-"+stamp
    try:
        for container in (CTRL,AGENT):
            archive=backup/(container+"-projects.tar")
            with archive.open("wb") as fd:
                run("docker","exec",container,"tar","-cf","-","-C",DATA,"projects",stdout=fd)
            with tarfile.open(archive) as tar:
                must(bool(tar.getmembers()),"empty gateway backup")
        evidence["backup_verified"]=True
        must(not present(staged) and not present(rejected) and not present(prior),
             "staging collision")
        source=ROOT/"factories/lab-warehouse/projects"/PROJECT
        existing=present(dst)
        identical=False
        if existing:
            try:
                verify_hashes(dst,expected)
                identical=True
            except (RuntimeError,subprocess.CalledProcessError):
                identical=False
        if identical:
            evidence["staging"]="PASS_ALREADY_IDENTICAL"
        else:
            # Before changing any installed TEST project, both Controller and
            # Agent project trees were archived above and validated.
            run("docker","cp",str(source),CTRL+":"+staged)
            run("docker","exec","-u","0",CTRL,"chown","-R","ignition:ignition",staged)
            verify_hashes(staged,expected)
            if existing:
                must(present(dst) and not present(prior),"project changed during stage")
                run("docker","exec",CTRL,"mv",dst,prior)
                replaced=True
            else:
                must(not present(dst),"project path appeared unexpectedly")
            run("docker","exec",CTRL,"mv",staged,dst)
            created=True
            evidence["staging"]="PASS_UPDATED_EXISTING_PROJECT" if replaced else "PASS_CREATED_NEW_PROJECT"
        verify_hashes(dst,expected)
        scan(token,ctx)
        verify_hashes(dst,expected)
        evidence["controller_scan"]="HTTP_ACCEPTED_AND_IDLE"
        if replaced:
            evidence["previous_version_preserved_at"]=prior
        evidence["status"]="CONTROLLER_STAGED_AND_SCANNED_NO_EAM"
        print("FRAMEWORK_FACTORY_A_CONTROLLER_STAGE_PASS")
        print("EAM_SEND_PROJECT=NOT_RUN")
    except Exception as e:
        evidence["error"]=str(e)
        if created or replaced:
            try:
                if present(dst):
                    run("docker","exec",CTRL,"mv",dst,rejected)
                if replaced and present(prior):
                    run("docker","exec",CTRL,"mv",prior,dst)
                    evidence["rollback"]="PRIOR_TEST_PROJECT_RESTORED"
                else:
                    evidence["rollback"]="NEW_TEST_PROJECT_REMOVED_FROM_DISCOVERY"
                scan(token,ctx)
            except Exception as rollback:
                evidence["rollback"]="ENGINEER_REQUIRED"
                evidence["rollback_error"]=str(rollback)
        raise
    finally:
        REPORT.parent.mkdir(exist_ok=True)
        REPORT.write_text(json.dumps(evidence,indent=2)+"\n")
        (backup/"evidence.json").write_text(json.dumps(evidence,indent=2)+"\n")

if __name__=="__main__":
    main()
