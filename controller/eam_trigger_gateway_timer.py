# Install ONLY in a Controller-local management project's Gateway Timer event.
# Fixed Delay 1000ms, Dedicated Thread. NEVER distribute this script to Agent.
from java.nio.file import Files, Paths
from java.nio.charset import StandardCharsets
import json

logger = system.util.getLogger('EAM-LAB-TRIGGER')
base = Paths.get('/usr/local/bin/ignition/data/eam-requests')
request = base.resolve('eam_request.json')
processing = base.resolve('eam_request.processing')

if Files.exists(request) and not Files.exists(processing):
    try:
        Files.move(request, processing)
        obj = json.loads(str(Files.readString(processing, StandardCharsets.UTF_8)))
        sha = obj.get('sha', '')
        if obj.get('project') != 'DeploymentSmokeTest' or obj.get('task') != 'Lab_Send_Project':
            raise Exception('Unexpected project or task')
        if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
            raise Exception('Invalid release SHA')
        result = system.eam.runTask('Lab_Send_Project')
        if result.getErrors() or result.getWarns():
            raise Exception('EAM returned warnings or errors: ' + str(result))
        receipt = base.resolve('started-' + sha + '.json')
        Files.writeString(receipt, json.dumps({'sha':sha,'task_invoked':True}), StandardCharsets.UTF_8)
        Files.deleteIfExists(processing)
        logger.info('EAM task invoked for ' + sha)
    except Exception as exc:
        logger.error('EAM-LAB-TRIGGER HOLD: ' + str(exc))
        # Processing file retained for explicit inspection; no automatic retry.
