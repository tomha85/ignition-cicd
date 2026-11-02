#!/usr/bin/env python3
"""Read-only LAB Ignition 8.3 EAM root-cause diagnostic.

Does not write Gateway config, call EAM tasks, restart services, install scripts,
create Agent projects, inspect secrets, or use undocumented mutation endpoints.
"""
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/eam-openapi-diagnostics.json"
CONTROLLER = "ignition-eam-controller"
AGENT = "ignition-eam-agent"
PROJECT = "FactoryASmoke"
P = "/usr/local/bin/ignition/data/projects/" + PROJECT
URL = "https://localhost:9143/openapi.json"


def cmd(*args):
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True,
                              timeout=20, check=False)
    except Exception:
        return None


def inspect_gateway(name):
    proc = cmd("inspect", "--format",
               "{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}",
               name)
    if proc is None or proc.returncode:
        return {"running": False, "health": "NOT_AVAILABLE"}
    terms = proc.stdout.strip().split("|")
    return {"running": terms[0] == "true", "health": terms[1] if len(terms) > 1 else "UNKNOWN"}


def project_status(container):
    proc = cmd("exec", container, "test", "-d", P)
    if proc is None:
        return "UNAVAILABLE"
    if proc.returncode == 1:
        return "ABSENT"
    if proc.returncode != 0:
        return "INACCESSIBLE"
    return "PRESENT"


def inspect_openapi(result, token, ca):
    if not ca or not Path(ca).is_file():
        result["openapi"] = {"status": "NO_TRUSTED_CA"}
        return
    if not token:
        result["openapi"] = {"status": "NO_AUTHORIZED_API_TOKEN"}
        return
    ctx = ssl.create_default_context(cafile=ca)
    req = urllib.request.Request(URL, headers={"X-Ignition-API-Token": token, "Accept":"application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as fd:
            if fd.status != 200:
                result["openapi"] = {"status": "HTTP_NOT_200", "http": fd.status}
                return
            spec = json.load(fd)
    except urllib.error.HTTPError as exc:
        result["openapi"] = {"status": "HTTP_DENIED_OR_MISSING", "http": exc.code}
        return
    except Exception as exc:
        # Only exception type, no token, response headers or URL query values.
        result["openapi"] = {"status": "UNAVAILABLE", "error_type": type(exc).__name__}
        return
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"),dict):
        result["openapi"] = {"status":"INVALID_SCHEMA"}
        return
    ops = []
    for path, methods in sorted(spec["paths"].items()):
        if re.search("eam|enterprise|agent.task|send.project",path,re.I):
            for method in ("get","post","put","patch","delete"):
                if isinstance(methods,dict) and method in methods:
                    op=methods[method]
                    desc=(str(op.get("summary") or "")+" "+str(op.get("operationId") or ""))
                    ops.append({"path":path, "method":method.upper(), "label":desc[:150]})
    # Do not claim task exists from OpenAPI route presence.
    result["openapi"]={"status":"AVAILABLE", "eam_related_operations":ops[:100],
                       "eam_operations_total":len(ops)}
    read_routes=[]
    for path, methods in spec["paths"].items():
        if re.search("agent.task|eam.*task",path,re.I) and "{" not in path and isinstance(methods,dict) and "get" in methods:
            read_routes.append(path)

    # Parse only public API schema metadata (no task payloads, credentials or OT addresses).
    goal="/data/api/v1/resources/com.inductiveautomation.eam/eam-tasks"
    op=spec["paths"].get(goal,{}) if isinstance(spec["paths"].get(goal),dict) else {}
    if isinstance(op.get("post"),dict):
        post=op["post"]
        body=post.get("requestBody",{})
        content=body.get("content",{}) if isinstance(body,dict) else {}
        schemas={mime: value.get("schema",{}) for mime,value in content.items()
                 if isinstance(value,dict)}
        result["openapi"]["create_task_contract"]={
            "route":goal,"requestBody_required":body.get("required",False) if isinstance(body,dict) else False,
            "content_types":list(content),
            "request_schemas":schemas,
            "parameters":[{"name":p.get("name"),"in":p.get("in")}
                          for p in post.get("parameters",[]) if isinstance(p,dict)]}
    target_components=spec.get("components",{}).get("schemas",{})
    def expand_refs(value,depth=0,seen=None):
        seen=set() if seen is None else seen
        if depth>4:return {"limit":"MAX_DEPTH"}
        if isinstance(value,list):
            return [expand_refs(v,depth+1,seen) for v in value[:12]]
        if not isinstance(value,dict):return value
        if "$ref" in value:
            ref=value["$ref"]
            key=ref.rsplit("/",1)[-1]
            if key in seen:return {"$ref":ref,"recursive":True}
            if key in target_components:
                return {"$ref":ref,"definition":expand_refs(target_components[key],depth+1,seen|{key})}
        return {key:expand_refs(v,depth+1,seen)
                for key,v in value.items() if key not in ("example","examples","description","default","externalDocs")}
    if "create_task_contract" in result["openapi"]:
        c=result["openapi"]["create_task_contract"]
        c["request_schemas_expanded"]={k:expand_refs(v) for k,v in c["request_schemas"].items()}

    # Compare the real, existing Factory A EAM task with the new smoke project.
    # Never expose raw resource JSON, credentials, internal addresses or secrets.
    path="/data/api/v1/resources/find/com.inductiveautomation.eam/eam-tasks/CICD-SEND-WarehouseHMI-A"
    task_req=urllib.request.Request("https://localhost:9143"+path,
        headers={"X-Ignition-API-Token":token,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(task_req,context=ctx,timeout=15) as resp:
            task=json.load(resp)
        def safe_summary(obj,level=0):
            if level>6:return "..."
            if isinstance(obj,list):return [safe_summary(x,level+1) for x in obj[:5]]
            if not isinstance(obj,dict):
                return obj if obj in ("EAM-Agent","WarehouseHMI","FactoryASmoke",
                    "CICD-SEND-WarehouseHMI-A","OnDemand","Immediate","eam_sendProject","Local System",
                    True,False,0,1) else type(obj).__name__
            return {k:safe_summary(v,level+1) for k,v in obj.items()
                    if not any(x in k.lower() for x in ("secret","credential","password","token","key","url","connection","certificate"))}
        result["openapi"]["legacy_task_definition"]={"http":200,"safe_shape":safe_summary(task)}
    except urllib.error.HTTPError as exc:
        result["openapi"]["legacy_task_definition"]={"http":exc.code}
    except Exception as exc:
        result["openapi"]["legacy_task_definition"]={"error_type":type(exc).__name__}
    # Supported route contract for forcing EAM task; NEVER call it in diagnostics.
    force="/data/eam/api/v1/eam-tasks/force/{owner}/{name}"
    force_methods=spec["paths"].get(force,{})
    result["openapi"]["force_task_api"]={
        "path":force,
        "methods": [k.upper() for k in force_methods if k.lower() in ("get","post","put","delete","patch")]
    }
    for method,specop in force_methods.items():
        if method.lower() in ("get","post") and isinstance(specop,dict):
            result["openapi"]["force_task_api"]["parameters"]=[
                {"name":p.get("name"),"in":p.get("in"),
                 "required":p.get("required",False)} for p in specop.get("parameters",[])
                if isinstance(p,dict)]
            result["openapi"]["force_task_api"]["request_body_present"]="requestBody" in specop

    # Extract only the exact legacy task route mapping and source identity.
    if "legacy_task_definition" in result["openapi"]:
        shape=result["openapi"]["legacy_task_definition"].get("safe_shape",{})
        settings=shape.get("config",{}).get("settings",{}) if isinstance(shape,dict) else {}
        result["openapi"]["legacy_task_safe_configuration"]={
            "sourceProject":settings.get("sourceProject"),
            "targetGateways_shape":settings.get("targetGateways"),
            "selectedGateway":settings.get("selectedGateway"),
            "profile":shape.get("config",{}).get("profile",{}),
        }
    # Read the official Agent-status endpoint using only GET.
    route="/data/eam/api/v1/agents"
    req=urllib.request.Request("https://localhost:9143"+route,
                headers={"X-Ignition-API-Token":token,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,context=ctx,timeout=15) as resp:
            agents=json.load(resp)
        if isinstance(agents,dict):
            payload=agents
        else:
            payload={"value":agents}
        txt=json.dumps(payload)
        result["openapi"]["agent_registry_summary"]={
            "http":200,"response_keys":list(payload.keys())[:30],
            "EAM-Agent_seen":"EAM-Agent" in txt,
            "response_type":type(agents).__name__
        }
        # Report fields of the exact approved EAM-Agent only. Others are elided.
        def matched(obj,depth=0):
            if depth>8:return []
            found=[]
            if isinstance(obj,dict):
                if any(v=="EAM-Agent" for v in obj.values() if isinstance(v,str)):
                    safe={}
                    for k,v in obj.items():
                        if k.lower() in ("name","id","agentname","gatewayname","status","state",
                                         "connected","connectionstatus","gatewaystatus","health"):
                            safe[k]=v if isinstance(v,(str,bool,int,float)) else type(v).__name__
                    if safe:found.append(safe)
                for v in obj.values():
                    found+=matched(v,depth+1)
            elif isinstance(obj,list):
                for v in obj[:30]:
                    found+=matched(v,depth+1)
            return found[:5]
        result["openapi"]["agent_registry_summary"]["matching_approved_agent"]=matched(agents)
    except urllib.error.HTTPError as exc:
        result["openapi"]["agent_registry_summary"]={"http":exc.code}
    except Exception as exc:
        result["openapi"]["agent_registry_summary"]={"error_type":type(exc).__name__}

    # Find the official EAM GET agents/status routes without inventing endpoints.
    result["openapi"]["agent_read_routes"]=[
        path for path,methods in sorted(spec["paths"].items())
        if ("agent" in path.lower() or "gateway-network" in path.lower())
        and ("status" in path.lower() or "agents" in path.lower())
        and "{" not in path and isinstance(methods,dict) and "get" in methods
    ][:35]

    # Direct documented read for registered EAM task names (do not expose all names).
    task_names="/data/api/v1/resources/names/com.inductiveautomation.eam/eam-tasks"
    req=urllib.request.Request("https://localhost:9143"+task_names,
               headers={"X-Ignition-API-Token":token,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,context=ctx,timeout=15) as resp:
            obj=json.load(resp)
        txt=json.dumps(obj)
        result["openapi"]["registered_task_summary"]={
            "http":200,"body_type":type(obj).__name__,
            "task_count":len(obj) if isinstance(obj,list) else None,
            "smoke_task":"PRESENT" if "CICD-SEND-FactoryASmoke-A" in txt else "NOT_FOUND",
            "legacy_task":"PRESENT" if "CICD-SEND-WarehouseHMI-A" in txt else "NOT_FOUND"}
    except urllib.error.HTTPError as exc:
        result["openapi"]["registered_task_summary"]={"http":exc.code}
    except Exception as exc:
        result["openapi"]["registered_task_summary"]={"error_type":type(exc).__name__}

    # GET only, only explicitly documented no-parameter EAM task routes.
    result["openapi"]["documented_task_read_routes"]=read_routes[:20]
    for path in read_routes[:5]:
        safe_req=urllib.request.Request("https://localhost:9143"+path,
                        headers={"X-Ignition-API-Token":token, "Accept":"application/json"})
        try:
            with urllib.request.urlopen(safe_req,context=ctx,timeout=15) as fd:
                d=json.load(fd)
            # Only inspect for explicitly allowlisted smoke task, no broad task data.
            serialized=json.dumps(d)
            result["openapi"].setdefault("task_inspection",[]).append({
                 "path":path, "http":200,
                 "smoke_task_name_visible": "CICD-SEND-FactoryASmoke-A" in serialized,
                 "legacy_factory_a_task_name_visible": "CICD-SEND-WarehouseHMI-A" in serialized,
                 "format":type(d).__name__})
        except urllib.error.HTTPError as exc:
            result["openapi"].setdefault("task_inspection",[]).append({"path":path,"http":exc.code})
        except Exception as exc:
            result["openapi"].setdefault("task_inspection",[]).append({"path":path,"error_type":type(exc).__name__})


def main():
    r={
      "timestamp_utc": datetime.now(timezone.utc).isoformat(),
      "mode":"READ_ONLY_LAB_DIAGNOSTICS",
      "factory":"lab-warehouse", "project":PROJECT, "environment":"test",
      "status":"HOLD_NOT_DEPLOYED",
      "e2e_agent_deployment":"NOT_RUN",
      "perspective_browser":"NOT_TESTED",
      "containers": {name:inspect_gateway(name) for name in (CONTROLLER,AGENT)},
      "controller_project":project_status(CONTROLLER),
      "agent_project":project_status(AGENT),
      "gateway_bridge":"NOT_VERIFIED",
      "eam_task":"NOT_VERIFIED",
    }
    # Gateway's openapi.json is the official discovery mechanism for 8.3.
    inspect_openapi(r, os.environ.get("IGNITION_CONTROLLER_API_TOKEN"),
                    os.environ.get("IGNITION_CONTROLLER_CA_FILE"))
    EVIDENCE.parent.mkdir(exist_ok=True)
    EVIDENCE.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r,indent=2))
    print("EAM_AGENT_DEPLOYMENT=NOT_RUN; DIAGNOSTICS_ONLY")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
