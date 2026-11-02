"""Evidence interpretation with explicit distinction between source/Controller/Agent."""
from reusable_cicd.core import FrameworkError


def controller_stage_verified(evidence: dict) -> bool:
    if not isinstance(evidence, dict):
        raise FrameworkError("invalid Controller evidence")
    return (evidence.get("backup_verified") is True
            and evidence.get("staging") in ("PASS_CREATED_NEW_PROJECT", "PASS_ALREADY_IDENTICAL")
            and evidence.get("controller_scan") == "HTTP_ACCEPTED_AND_IDLE"
            and evidence.get("status") == "CONTROLLER_STAGED_AND_SCANNED_NO_EAM")


def agent_e2e_verified(_evidence: dict) -> bool:
    """No Agent EAM/browser/FAT evidence has been independently qualified."""
    return False
