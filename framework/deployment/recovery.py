"""No automatic production recovery without a reviewed, verified restore plan."""
from reusable_cicd.core import FrameworkError

def automatic_production_rollback(*_args, **_kwargs):
    raise FrameworkError("HOLD: production rollback must be reviewed, restored and reverified")
