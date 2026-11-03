"""Fail-closed tests for approved TEST EAM task handoff."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import auto_send_existing_eam_task as m
from framework.security.policies import check_target_registry
from reusable_cicd.core import FrameworkError


class AutoEamTaskTests(unittest.TestCase):
    def test_commissioned_task_is_exactly_scoped(self):
        target, task = m.eligible_task(m.ROOT, "lab-warehouse", "warehouse-main", "WarehouseHMI")
        self.assertTrue(target["eam_send_commissioned"])
        self.assertEqual(task, {"project": "WarehouseHMI", "task_name": "CICD-SEND-WarehouseHMI-A", "agent_name": "EAM-Agent"})

    def test_task_requires_correct_agent(self):
        agents = {"items": [{"name": "EAM-Agent", "id": "agent-001"}]}
        self.assertTrue(m.agent_id_matches(agents, "EAM-Agent", "agent-001"))
        self.assertFalse(m.agent_id_matches(agents, "EAM-Agent", "agent-002"))
        self.assertFalse(m.agent_id_matches(agents, "Other", "agent-001"))
        self.assertFalse(m.agent_id_matches({"items": [agents["items"][0]] * 2},
                                           "EAM-Agent", "agent-001"))

    def test_other_warehouse_project_not_authorized_for_eam(self):
        target, task = m.eligible_task(m.ROOT, "lab-warehouse", "warehouse-main", "FactoryASmoke")
        self.assertTrue(target["eam_send_commissioned"])
        self.assertIsNone(task)

    def test_commissioning_requires_reviewed_task_binding(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(m.ROOT / "factories", root / "factories")
            (root / "targets").mkdir()
            registry = json.loads((m.ROOT / "targets/lab-targets.json").read_text())
            registry["targets"][0]["eam_send_commissioned"] = True
            registry["targets"][0]["eam_tasks"] = []
            (root / "targets/lab-targets.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(FrameworkError, "binding"):
                check_target_registry(root)

    def test_production_never_authorized(self):
        target, _ = m.eligible_task(m.ROOT, "lab-warehouse",
                                    "warehouse-main", "WarehouseHMI")
        self.assertFalse(target["production_approved"])


if __name__ == "__main__":
    unittest.main()
