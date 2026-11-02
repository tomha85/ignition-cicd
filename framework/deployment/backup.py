"""Assess test archive metadata only; a project tar is not a full Gateway backup."""
from pathlib import Path
from reusable_cicd.core import FrameworkError

def verify_project_archives(paths: list[Path]) -> dict:
    import tarfile
    if not isinstance(paths, list) or not paths:
        raise FrameworkError("missing TEST project directory backups")
    for path in paths:
        if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0:
            raise FrameworkError("unreadable TEST archive: " + str(path))
        with tarfile.open(path, "r:") as archive:
            if not archive.getmembers():
                raise FrameworkError("empty TEST project archive")
    return {"project_archives_verified": len(paths),
            "full_gateway_backup": "NOT_VERIFIED"}
