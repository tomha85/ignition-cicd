#!/usr/bin/env bash
# TEST ONLY: back up Controller & Agent, then stage WarehouseHMI on Controller.
# Does NOT copy anything to Agent or invoke EAM Send Project.
set -euo pipefail
test "${FACTORY_A_TEST_CONFIRM:-}" = "YES" || { echo "HOLD: set FACTORY_A_TEST_CONFIRM=YES"; exit 2; }
ROOT="${1:-$HOME/ignition-cicd}"
cd "$ROOT"
test -f ignition-project/WarehouseHMI/project.json || { echo "HOLD: WarehouseHMI source missing"; exit 2; }
for c in ignition-eam-controller ignition-eam-agent; do
  test "$(docker inspect -f '{{.State.Running}}' "$c")" = true || { echo "HOLD: $c not running"; exit 2; }
done
BASE="${FACTORY_A_BACKUP_ROOT:-$HOME/ignition-eam-lab/backups}"
mkdir -p "$BASE"
test "$BASE" != "$ROOT" || exit 2
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="$BASE/factory-a-$STAMP"
mkdir -m 700 "$OUT"
for c in ignition-eam-controller ignition-eam-agent; do
  docker exec "$c" tar -C /usr/local/bin/ignition/data -cf - projects > "$OUT/$c-projects.tar"
  tar -tf "$OUT/$c-projects.tar" >/dev/null
done
echo "BACKUPS_VERIFIED=$OUT"
DST="/usr/local/bin/ignition/data/projects/WarehouseHMI"
if docker exec ignition-eam-controller test -e "$DST"; then
  echo "HOLD: Controller WarehouseHMI already exists; do not overwrite"
  exit 2
fi
docker cp ignition-project/WarehouseHMI ignition-eam-controller:"$DST"
docker exec -u 0 ignition-eam-controller chown -R ignition:ignition "$DST"
python3 - <<'PY'
from pathlib import Path
import subprocess,hashlib
p=Path("ignition-project/WarehouseHMI")
dst="/usr/local/bin/ignition/data/projects/WarehouseHMI"
for f in sorted(p.rglob("*")):
    if not f.is_file():continue
    rel=f.relative_to(p).as_posix()
    a=hashlib.sha256(f.read_bytes()).hexdigest()
    b=subprocess.check_output(["docker","exec","ignition-eam-controller","sha256sum",dst+"/"+rel],text=True).split()[0]
    if a!=b:raise SystemExit("HOLD: hash mismatch "+rel)
print("CONTROLLER_FILES_MATCH=PASS")
PY
echo "CONTROLLER_STAGED=PASS"
echo "NEXT=Run authenticated Controller project scan; verify WarehouseHMI in Controller Projects"
echo "NEXT=Create on-demand EAM Send Project task CICD-SEND-WarehouseHMI-A targeting EAM-Agent"
echo "NOTE=Agent remains unchanged; EAM task has NOT been invoked"
