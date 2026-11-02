"""Authenticated TEST Controller scan; checks project visible via local source filesystem after scan."""
import json
import os
import ssl
import time
from pathlib import Path
from urllib.request import Request, urlopen

token=os.environ.get("IGNITION_CONTROLLER_API_TOKEN")
ca=Path(os.environ.get("IGNITION_CONTROLLER_CA_FILE",""))
if not token or not ca.is_file():
    raise SystemExit("HOLD: trusted CA/token missing")
url="https://localhost:9143/data/api/v1/scan/projects"
context=ssl.create_default_context(cafile=str(ca))
headers={"X-Ignition-API-Token":token}
with urlopen(Request(url,data=b"",method="POST",headers=headers),timeout=30,context=context) as r:
    if not 200 <= r.status < 300:
        raise SystemExit("HOLD: Controller scan rejected")
deadline=time.monotonic()+90
while time.monotonic()<deadline:
    with urlopen(Request(url,headers=headers),timeout=30,context=context) as r:
        status=json.load(r)
    if status.get("scanActive") is False:
        print("CONTROLLER_SCAN_IDLE=PASS")
        print("NOTE: Ignition runtime project visibility still requires Gateway UI verification")
        break
    time.sleep(2)
else:
    raise SystemExit("HOLD: project scan still active")
