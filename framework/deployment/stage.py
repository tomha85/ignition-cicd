"""Dynamic compatibility bridge to verified manifest/TEST target staging policy."""
from reusable_cicd.core import FrameworkError
from scripts.manual_factory_dispatch import authorize_stage

def validate_stage_authority(factory: str, gateway: str, project: str) -> dict:
    target = authorize_stage(factory, gateway, project)
    return {"approved_controller_stage": True, "target_id": target["target_id"], "factory_id": factory,
            "gateway_id": gateway, "project": project,
            "eam_agent_deploy": False, "production_deploy": False}

def stage_uncommissioned(*_args, **_kwargs):
    raise FrameworkError("HOLD: TEST Controller target must be commissioned before staging")
