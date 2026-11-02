"""Contract for requested standard repository layout."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class StandardRepositoryLayoutTest(unittest.TestCase):
    def test_workflow_entrypoints(self):
        for name in ("validate.yml","build-release.yml","deploy-test.yml","reusable-deploy.yml"):
            self.assertTrue((ROOT/".github/workflows"/name).is_file(),name)

    def test_engine_modules(self):
        for name in ("manifest.py","projects.py","gateway_config.py"):
            self.assertTrue((ROOT/"framework/validation"/name).is_file(),name)
        for name in ("ignition_83.py","eam.py","docker_lab.py"):
            self.assertTrue((ROOT/"framework/adapters"/name).is_file(),name)
        for name in ("planner.py","backup.py","stage.py","deploy.py","verify.py","recovery.py"):
            self.assertTrue((ROOT/"framework/deployment"/name).is_file(),name)

    def test_all_test_layers(self):
        for part in ("unit","integration","gateway","fat"):
            self.assertTrue((ROOT/"tests"/part/"__init__.py").is_file())
            
    def test_docs_and_existing_factories(self):
        for name in ("architecture.md","add-factory.md","developer-guide.md","deployment-guide.md"):
            self.assertTrue((ROOT/"docs"/name).is_file())
        for name in ("lab-warehouse","lab-assembly","lab-packaging"):
            for section in ("factory.json","projects","gateways","environments","tests/requirements.json"):
                self.assertTrue((ROOT/"factories"/name/section).exists(),name+"/"+section)

if __name__=="__main__":unittest.main()
