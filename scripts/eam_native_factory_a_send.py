#!/usr/bin/env python3
"""One-shot, allowlisted TEST-only native EAM project transfer using Ignition 8.3 OpenAPI.

No arbitrary factory/Agent/project parameters. No Controller Timer, task shell hacks
or direct Agent deployment. Backup both Gateways BEFORE creating/running the EAM task.
Existing task definitions and existing Agent projects are never overwritten.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reusable_cicd.core import FrameworkError
from framework.validation.structure import qualify_repository
from framework.deployment.planner import plan_test

CONTROLLER="ignition-eam-controller"
AGENT="ignition-eam-agent"
PROJECT="FactoryASmoke"
FACTORY="lab-warehouse"
GATEWAY="warehouse-main"
TASK="CICD-SEND-FactoryASmoke-A"
LEGACY="CICD-SEND-WarehouseHMI-A"
RESOURCE="/data/api/v1/resources/com.inductiveautomation.eam/eam-tasks"
FIND="/data/api/v1/resources/find/com.inductiveautomation.eam/eam-tasks/"
AGENTS="/data/eam/api/v1/agents"
FORCE="/data/eam/api/v1/eam-tasks/force/"
DATA="/usr/local/bin/ignition/data"
ROOT_URL="https://localhost:9143"
EVIDENCE=ROOT/"evidence/eam-factory-a-native-send-project.json"
GCU="/usr/local/bin/ignition/gwcmd.sh"


def require(test,reason):
    if not test:raise RuntimeError("HOLD: "+reason)


def run(*args,stdout=None):
    return subprocess.run(args,stdout=stdout,stderr=subprocess.PIPE,
                          check=True,timeout=150)


def output(*args):
    return subprocess.check_output(args,stderr=subprocess.PIPE,text=True,timeout=25).strip()


def exists(container,path):
    p=subprocess.run(["docker","exec",container,"test","-e",path],
                     capture_output=True,timeout=20)
    require(p.returncode in (0,1),"cannot inspect "+container)
    return p.returncode==0


def api(path,ctx,token,method="GET",body=None):
    req=Request(ROOT_URL+path,method=method,
                data=json.dumps(body).encode("utf-8") if body is not None else
                     (b"" if method=="POST" else None),
                headers={"X-Ignition-API-Token":token,
                         "Content-Type":"application/json","Accept":"application/json"})
    try:
        with urlopen(req,context=ctx,timeout=35) as r:
            raw=r.read()
            if not raw:return {"http":r.status}
            try:return json.loads(raw)
            except ValueError:return {"http":r.status,"content_type":"non_json"}
    except HTTPError as exc:
        # Never print error response bodies or authenticated request headers.
        raise RuntimeError("HOLD: Gateway API "+method+" "+path.split("/")[2]+
                           " returned HTTP "+str(exc.code)) from None


def find_task(ctx,token,name):
    try:
        return api(FIND+quote(name,safe=""),ctx,token)
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):return None
        raise


def healthy(container):
    state=output("docker","inspect","--format",
                 "{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}",
                 container)
    return state=="true|healthy"


def verify_native_files(container,source_hashes,expected_all=False):
    base=DATA+"/projects/"+PROJECT
    if not exists(container,base):return "ABSENT"
    # Native EAM may regenerate resource metadata on receive. The actual
    # Perspective view & page-config must match exactly; don't invent runtime PASS.
    keys=sorted(source_hashes) if expected_all else [
        "com.inductiveautomation.perspective/views/Main/view.json",
        "com.inductiveautomation.perspective/page-config/config.json",
        "project.json"]
    for rel in keys:
        try:
            actual=output("docker","exec",container,"sha256sum",base+"/"+rel).split()[0]
        except Exception:
            return "MISSING_"+rel
        if actual!=source_hashes[rel]:
            return "HASH_MISMATCH_"+rel
    return "FILES_MATCH"


def backup_gateway(container,directory,stamp):
    require(exists(container,GCU),"Gateway backup command missing "+container)
    remote="/tmp/eam-factory-a-"+stamp+".gwbk"
    require(not exists(container,remote),"backup path exists; refuse collision")
    run("docker","exec",container,GCU,"-b",remote)
    require(exists(container,remote),"Gateway backup not created "+container)
    dest=directory/(container+"-FULL-GATEWAY.gwbk")
    run("docker","cp",container+":"+remote,str(dest))
    # Some versions wrap a proprietary header; rely on size + GCU success.
    require(dest.stat().st_size>8192,"Gateway full backup suspiciously small")
    project_tar=directory/(container+"-projects.tar")
    with project_tar.open("wb") as stream:
        run("docker","exec",container,"tar","-cf","-","-C",DATA,"projects",stdout=stream)
    with tarfile.open(project_tar) as tar:
        require(bool(tar.getmembers()),"empty project backup "+container)
    return {"file":dest.name, "size":dest.stat().st_size,
            "sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),
            "project_archive":project_tar.name}


def match_approved_agent(agents,target_id):
    # A task target ID must resolve to the registered EAM-Agent record, not
    # merely appear somewhere in the response for another Agent.
    def walk(value):
        if isinstance(value,list):
            for it in value:yield from walk(it)
        if isinstance(value,dict):
            if value.get("name")=="EAM-Agent":
                yield value
            for v in value.values():
                if isinstance(v,(dict,list)):yield from walk(v)
    matches=list(walk(agents))
    if len(matches)!=1:return False
    record=matches[0]
    return any(v==target_id for v in record.values() if isinstance(v,str)) or (
        target_id=="EAM-Agent" and record.get("name")=="EAM-Agent")


def agent_http():
    from urllib.error import HTTPError
    url="http://localhost:9288/data/perspective/client/"+PROJECT
    try:
        with urlopen(Request(url),timeout=20) as r:
            return "HTTP_200_NOT_BROWSER_RENDERED" if r.status==200 else "HTTP_"+str(r.status)
    except HTTPError as exc:
        return "HTTP_"+str(exc.code)
    except Exception:
        return "NOT_REACHABLE"


def provision_and_run(sha):
    require(os.environ.get("GITHUB_REPOSITORY")=="tomha85/ignition-cicd","repo allowlist")
    require(os.environ.get("GITHUB_REF")=="refs/heads/feat/reusable-multifactory-framework-v1","branch allowlist")
    require(os.environ.get("GITHUB_EVENT_NAME")=="push","one-shot branch push only")
    require(os.environ.get("GITHUB_SHA")==sha and re.fullmatch("[0-9a-f]{40}",sha),"immutable SHA mismatch")
    require(os.environ.get("EAM_NATIVE_FACTORY_A_SMOKE_CONFIRM")=="YES_FACTORY_A_TEST_ONLY","LAB scope confirmation")
    qualify_repository(ROOT)
    plan=plan_test(ROOT,FACTORY,GATEWAY,PROJECT,sha)
    source_hashes=plan["source_hashes"]
    for c in (CONTROLLER,AGENT):
        require(healthy(c),"LAB Gateway unhealthy "+c)
    require(verify_native_files(CONTROLLER,source_hashes)=="FILES_MATCH",
            "Controller project files differ from Git SHA")
    dest=DATA+"/projects/"+PROJECT
    require(not exists(AGENT,dest),"TEST Agent already contains this project: no overwrite")
    ca=Path(os.environ.get("IGNITION_CONTROLLER_CA_FILE") or "")
    token=os.environ.get("IGNITION_CONTROLLER_API_TOKEN")
    require(bool(token) and ca.is_file(),"authorized HTTPS Controller API missing")
    ctx=ssl.create_default_context(cafile=str(ca))
    spec=api("/openapi.json",ctx,token)
    paths=spec.get("paths",{})
    require("post" in paths.get(RESOURCE,{}),"native EAM task creation API unavailable")
    require("post" in paths.get("/data/eam/api/v1/eam-tasks/force/{owner}/{name}",{}),
            "native EAM task execution API unavailable")
    old=find_task(ctx,token,LEGACY)
    require(isinstance(old,dict),"verified legacy Send Project template not present")
    profile=old.get("config",{}).get("profile",{})
    settings=old.get("config",{}).get("settings",{})
    require(old.get("name")==LEGACY and profile.get("type")=="eam_sendProject",
            "legacy template is not a Send Project task")
    require(profile.get("scheduleMode")=="OnDemand" and not profile.get("isSuspended",False),
            "legacy template not enabled for OnDemand")
    require(settings.get("sourceProject")=="WarehouseHMI" and
            settings.get("selectedGateway")=="__local__","legacy task source not local")
    require(settings.get("targetGroups")==[],"legacy task targets group; not allowed")
    target_ids=settings.get("targetGateways")
    require(isinstance(target_ids,list) and len(target_ids)==1 and
            isinstance(target_ids[0],str),"legacy task must target exactly one Agent")
    agents=api(AGENTS,ctx,token)
    require(match_approved_agent(agents,target_ids[0]),"configured target is not EAM-Agent")
    require(old.get("collection")=="core","unrecognized task collection")
    owner=old.get("healthchecks",{}).get("scheduledTaskState",{}).get("result",{}).get("details",{}).get("owner")
    require(owner=="eam","unexpected EAM task owner")
    require(find_task(ctx,token,TASK) is None,"existing FactoryASmoke task: no overwrite")
    backup_path=os.environ.get("IGNITION_BACKUP_DIR","")
    require(bool(backup_path),"LAB backup directory required")
    root=Path(backup_path).expanduser().resolve()
    require(root.is_dir() and root!=ROOT and ROOT not in root.parents,
            "unsafe or missing backup directory")
    stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+uuid.uuid4().hex[:8]
    backup=root/("eam-native-factory-a-"+stamp)
    backup.mkdir(mode=0o700)
    os.chmod(backup,0o700)
    report={"mode":"NATIVE_EAM_FACTORY_A_TEST_ONLY",
            "factory":FACTORY,"gateway":GATEWAY,"project":PROJECT,
            "release_sha":sha,"status":"HOLD","task_name":TASK,
            "backup_directory":str(backup),"controller_backup":"NOT_RUN",
            "agent_backup":"NOT_RUN","eam_task_create":"NOT_RUN",
            "eam_task_execute":"NOT_RUN","agent_verification":"NOT_RUN",
            "perspective_http":"NOT_TESTED","browser_render":"NOT_TESTED",
            "production":"FORBIDDEN"}
    try:
        for container,key in ((CONTROLLER,"controller_backup"),(AGENT,"agent_backup")):
            report[key]=backup_gateway(container,backup,stamp)
        report["backups_verified_before_mutation"]=True
        require(not exists(AGENT,dest),"Agent project appeared before provisioning")
        config=copy.deepcopy(old["config"])
        config["profile"]["type"]="eam_sendProject"
        config["profile"]["scheduleMode"]="OnDemand"
        config["profile"]["isSuspended"]=False
        config["settings"]["sourceProject"]=PROJECT
        config["settings"]["selectedGateway"]="__local__"
        config["settings"]["targetGateways"]=[target_ids[0]]
        config["settings"]["targetGroups"]=[]
        config["settings"]["maxConcurrentAgents"]=1
        config["settings"]["controllerIsTargetKey"]=False
        payload=[{"name":TASK,"collection":"core","enabled":True,
                  "description":"Isolated TEST FactoryASmoke -> EAM-Agent; GitHub "+sha[:12],
                  "config":config}]
        # Native documented Ignition resource API; no internal DB mutations.
        api(RESOURCE,ctx,token,method="POST",body=payload)
        report["eam_task_create"]="API_REQUEST_ACCEPTED"
        task=None
        for i in range(12):
            task=find_task(ctx,token,TASK)
            if isinstance(task,dict):break
            time.sleep(2)
        require(isinstance(task,dict),"new EAM task not discoverable")
        current=task.get("config",{})
        st=current.get("settings",{})
        require(current.get("profile",{}).get("type")=="eam_sendProject" and
                current.get("profile",{}).get("scheduleMode")=="OnDemand" and
                st.get("sourceProject")==PROJECT and
                st.get("targetGateways")==[target_ids[0]] and
                st.get("selectedGateway")=="__local__",
                "created EAM task config not verified")
        report["eam_task_create"]="REGISTERED_AND_TARGET_VERIFIED"
        require(not exists(AGENT,dest),"Agent project appeared before EAM Send Project")
        # Exact documented EAM execution endpoint; this is the ONLY Agent mutation.
        force=FORCE+quote(owner,safe="")+"/"+quote(TASK,safe="")
        api(force,ctx,token,method="POST")
        report["eam_task_execute"]="ON_DEMAND_API_ACCEPTED"
        deadline=time.monotonic()+180
        last="ABSENT"
        while time.monotonic()<deadline:
            last=verify_native_files(AGENT,source_hashes)
            if last=="FILES_MATCH":break
            time.sleep(3)
        report["agent_verification"]=last
        require(last=="FILES_MATCH","EAM task ran but Agent native project did not match")
        report["perspective_http"]=agent_http()
        report["status"]="EAM_SEND_PROJECT_AND_AGENT_NATIVE_FILES_PASS"
        print("EAM_FACTORY_A_AGENT_SOURCE_PASS")
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        report["error"]=str(exc)[:550]
        raise
    finally:
        EVIDENCE.parent.mkdir(parents=True,exist_ok=True)
        EVIDENCE.write_text(json.dumps(report,indent=2)+"\n")
        (backup/"evidence.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


def main():
    if len(sys.argv)!=2:raise SystemExit("usage: python eam_native_factory_a_send.py <40hexGitSHA>")
    # Always capture diagnostics in the GitHub evidence log; never print API tokens.
    print(json.dumps(provision_and_run(sys.argv[1]),indent=2))


if __name__=="__main__":
    main()
