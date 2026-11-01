# Controller-only Ignition Gateway Timer script, isolated project.
# Configure Fixed Delay 1000 ms, Dedicated Thread.
# Do NOT deploy this management project using the smoke-test EAM task.
from java.nio.file import Files, Paths
from java.nio.charset import StandardCharsets
import json

logger = system.util.getLogger('EAM-LAB-TRIGGER')
REQUEST_DIR = '/mnt/eam-requests'
request = Paths.get(REQUEST_DIR, 'eam_request.json')

if Files.exists(request):
    claimed = Paths.get(REQUEST_DIR, 'eam_request.processing')
    if not Files.exists(claimed):
        try:
            Files.move(request, claimed)
            obj = json.loads(str(Files.readString(claimed, StandardCharsets.UTF_8)))
            if obj.get('project') != 'DeploymentSmokeTest' or obj.get('task') != 'Lab_Send_Project':
                raise Exception('Unexpected project/task')
            sha = obj.get('sha', '')
            if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
                raise Exception('Invalid SHA')
            # HOLD: must verify Controller has loaded this SHA before running task.
            result = system.eam.runTask('Lab_Send_Project')
            receipt = Paths.get(REQUEST_DIR, 'started-' + sha + '.json')
            Files.writeString(receipt, json.dumps({'sha': sha, 'task_invoked': True, 'result': str(result)}), StandardCharsets.UTF_8)
            Files.deleteIfExists(claimed)
            logger.info('EAM runTask invoked for ' + sha)
        except Exception as exc:
            logger.error('EAM trigger failure: ' + str(exc))
            # Keep processing file for investigation; no automatic retry.
