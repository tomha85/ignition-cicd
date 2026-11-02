"""Deliberately narrow compatibility bridge to the existing tested Controller smoke."""
from reusable_cicd.core import FrameworkError
from scripts.manual_factory_dispatch import authorize_stage

def validate_stage_authority(factory: str, gateway: str, project: str) -> dict:
    authorize_stage(factory, gateway, project)
    return {"approved_controller_stage": True, "factory_id": factory,
            "gateway_id": gateway, "project": project,
            "eam_agent_deploy": False, "production_deploy": False}

def stage_uncommissioned(*_args, **_kwargs):
    raise FrameworkError("HOLD: only the existing audited TEST smoke adapter may stage Controller files")
