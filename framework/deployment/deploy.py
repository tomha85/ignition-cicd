"""Agent and production deployment stay behind independent commissioning gates."""
from reusable_cicd.core import FrameworkError

def deploy_eam_agent(*_args, **_kwargs):
    raise FrameworkError(
        "HOLD: generic EAM Send Project to selected Agent is NOT COMMISSIONED; "
        "Controller staging PASS does not prove Agent or Perspective runtime"
    )
