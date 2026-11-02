# Ignition Gateway Timer script; install ONLY on TEST EAM Controller management project.
# Timer fixed delay (e.g. 2000 ms), one dedicated thread.
# Uses the immutable allowlist below; NO arbitrary task names permitted.
from java.nio.file import Files, Paths
from java.nio.charset import StandardCharsets
import json
import re

ROOT = Paths.get("/usr/local/bin/ignition/data/eam-multi-factory-requests")
REQUEST = ROOT.resolve("request.json")
PROCESSING = ROOT.resolve("request.processing")
ALLOWED = {
    "factory_a": ("WarehouseHMI", "EAM-Factory-A", "CICD-SEND-WarehouseHMI-A"),
    "factory_b": ("ConveyorHMI", "EAM-Factory-B", "CICD-SEND-ConveyorHMI-B"),
    "factory_c": ("PackagingHMI", "EAM-Factory-C", "CICD-SEND-PackagingHMI-C"),
}
log = system.util.getLogger("DEVAGENT-EAM-TEST")

if Files.exists(REQUEST) and not Files.exists(PROCESSING):
    try:
        Files.move(REQUEST, PROCESSING)
        request = json.loads(str(Files.readString(PROCESSING, StandardCharsets.UTF_8)))
        factory = request.get("factory")
        approved = ALLOWED.get(factory)
        if approved is None or (request.get("project"), request.get("target_agent"), request.get("eam_task")) != approved:
            raise Exception("Unauthorized factory/project/Agent/task")
        release = request.get("release_sha", "")
        request_id = request.get("request_id", "")
        if not re.match("^[0-9a-f]{40}$", release):
            raise Exception("Invalid release SHA")
        if not re.match("^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{10}$", request_id):
            raise Exception("Invalid request id")
        # runTask() response proves invocation only, NOT remote task completion.
        response = system.eam.runTask(approved[2])
        if response.getErrors() or response.getWarns():
            raise Exception("EAM task invocation returned errors or warnings")
        receipt = {"request_id": request_id, "eam_task": approved[2], "task_invoked": True}
        Files.writeString(ROOT.resolve("invoked-" + request_id + ".json"),
                          json.dumps(receipt), StandardCharsets.UTF_8)
        Files.deleteIfExists(PROCESSING)
        log.info("TEST EAM task invoked for " + factory + " request " + request_id)
    except Exception as exc:
        # Intentionally leave .processing as a dead-letter; never auto-retry.
        log.error("TEST EAM task HOLD: " + str(exc))
