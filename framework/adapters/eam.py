"""EAM adapter contract: do not turn a Controller-stage receipt into Agent PASS."""
from framework.deployment.deploy import deploy_eam_agent

def send_project_to_agent(*args, **kwargs):
    return deploy_eam_agent(*args, **kwargs)
