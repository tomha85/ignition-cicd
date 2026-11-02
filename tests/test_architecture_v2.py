"""Architecture V2 regression suite; NO live Gateway, Docker, PLC or EAM calls."""
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from reusable_cicd.core import FrameworkError
from framework.validation.structure import qualify_repository
from framework.validation.source_sync import check_mirrors, compare_native_project_trees
from framework.validation.environments import check_environments
from framework.validation.gateway_config import inspect_gateway
from framework.security.policies import check_target_registry, require_production_authorization
from framework.deployment.planner import plan_test
from framework.deployment.deploy import deploy_eam_agent
from framework.deployment.stage import validate_stage_authority
from framework.deployment.verify import controller_stage_verified, agent_e2e_verified
from framework.deployment.backup import verify_project_archives

ROOT = Path(__file__).resolve().parents[1]
SHA = "a"*40

class ArchitectureV2Tests(unittest.TestCase):
    def test_full_structure(self):
        d=qualify_repository(ROOT)
        self.assertEqual(d["status"],"STRUCTURE_VALIDATED_DEPLOYMENT_NOT_AUTHORIZED")
        self.assertEqual(d["factories"],["lab-assembly","lab-packaging","lab-warehouse"])
        self.assertFalse(d["production_approved"])
        self.assertEqual(d["eam_agent_transfer"],"NOT_TESTED")

    def test_environment_mapping(self):
        self.assertEqual(check_environments(ROOT)["environment_documents"],9)

    def test_curated_gateway_config(self):
        for f,g in (("lab-warehouse","warehouse-main"),
                    ("lab-assembly","assembly-main"),
                    ("lab-assembly","utilities-main"),
                    ("lab-packaging","packaging-main")):
            d=inspect_gateway(ROOT,f,g)
            self.assertEqual(d["resource_count"],0)
            self.assertFalse(d["deployment_enabled"])
            self.assertEqual(d["physical_mapping"],"NOT_VERIFIED")

    def test_source_mirrors(self):
        self.assertEqual(check_mirrors(ROOT)["mirror_pairs"],3)
        self.assertEqual(check_mirrors(ROOT)["verified_files"],15)

    def test_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); a=root/"factories/f/projects/HMI"; b=root/"ignition-project/HMI"
            a.mkdir(parents=True); b.mkdir(parents=True)
            (a/"project.json").write_text("{}")
            (b/"project.json").write_text("{}")
            self.assertEqual(compare_native_project_trees(root,"factories/f/projects/HMI","ignition-project/HMI"),1)
            (b/"project.json").write_text('{"modified":true}')
            with self.assertRaisesRegex(FrameworkError,"drift"):
                compare_native_project_trees(root,"factories/f/projects/HMI","ignition-project/HMI")

    def test_source_path_escape_rejected(self):
        with self.assertRaises(FrameworkError):
            compare_native_project_trees(ROOT,"factories/../x","ignition-project/x")

    def test_source_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); a=root/"factories/f/projects/HMI"; b=root/"ignition-project/HMI"
            a.mkdir(parents=True); b.mkdir(parents=True)
            (a/"project.json").write_text("{}")
            (b/"project.json").symlink_to(a/"project.json")
            with self.assertRaises(FrameworkError):
                compare_native_project_trees(root,"factories/f/projects/HMI","ignition-project/HMI")

    def test_environment_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copytree(ROOT/"factories",root/"factories")
            path=root/"factories/lab-warehouse/environments/test.json"
            obj=json.loads(path.read_text())
            obj["gateways"]["warehouse-main"]["target_id"]="another-site"
            path.write_text(json.dumps(obj))
            with self.assertRaisesRegex(FrameworkError,"drift"):
                check_environments(root)

    def test_gateway_deploy_flag_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dest=root/"factories/lab-warehouse/gateways/warehouse-main/config"
            dest.mkdir(parents=True)
            source=ROOT/"factories/lab-warehouse/gateways/warehouse-main/config/gateway.json"
            obj=json.loads(source.read_text())
            obj["deployment_enabled"]=True
            (dest/"gateway.json").write_text(json.dumps(obj))
            with self.assertRaisesRegex(FrameworkError,"disabled"):
                inspect_gateway(root,"lab-warehouse","warehouse-main")

    def test_test_target_registry_deny_eam(self):
        d=check_target_registry(ROOT)
        self.assertEqual(d["registered_test_targets"],4)
        self.assertFalse(d["eam_send_commissioned"])
        self.assertFalse(d["production_approved"])

    def test_production_block(self):
        with self.assertRaisesRegex(FrameworkError,"HOLD"):
            require_production_authorization("lab-warehouse")

    def test_agent_deploy_block(self):
        with self.assertRaisesRegex(FrameworkError,"HOLD"):
            deploy_eam_agent("lab-warehouse")

    def test_commissioned_controller_scope(self):
        allowed=validate_stage_authority("lab-warehouse","warehouse-main","FactoryASmoke")
        self.assertTrue(allowed["approved_controller_stage"])
        self.assertFalse(allowed["eam_agent_deploy"])
        other=validate_stage_authority("lab-warehouse","warehouse-main","WarehouseHMI")
        self.assertTrue(other["approved_controller_stage"])
        with self.assertRaises(FrameworkError):
            validate_stage_authority("lab-assembly","assembly-main","ConveyorHMI")

    def test_release_plan_is_dry_run(self):
        d=plan_test(ROOT,"lab-warehouse","warehouse-main","FactoryASmoke",SHA)
        self.assertEqual(d["status"],"VALIDATED_NOT_DEPLOYED")
        self.assertFalse(d["agent_deployed"])
        self.assertEqual(d["gateway_runtime"],"NOT_TESTED")

    def test_wrong_gateway_project_block(self):
        with self.assertRaises(FrameworkError):
            plan_test(ROOT,"lab-assembly","utilities-main","ConveyorHMI",SHA)

    def test_controller_stage_is_not_agent_pass(self):
        proof={"backup_verified":True,"staging":"PASS_ALREADY_IDENTICAL",
               "controller_scan":"HTTP_ACCEPTED_AND_IDLE",
               "status":"CONTROLLER_STAGED_AND_SCANNED_NO_EAM"}
        self.assertTrue(controller_stage_verified(proof))
        self.assertFalse(agent_e2e_verified(proof))
        proof["controller_scan"]="NOT_RUN"
        self.assertFalse(controller_stage_verified(proof))

    def test_project_archive_not_gateway_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"projects.tar"; src=Path(tmp)/"project.json"
            src.write_text("{}")
            with tarfile.open(p,"w") as tf:
                tf.add(src,arcname="projects/Smoke/project.json")
            self.assertEqual(verify_project_archives([p])["full_gateway_backup"],"NOT_VERIFIED")

    def test_schemas_are_valid_json(self):
        files=list((ROOT/"shared/schemas").glob("*.json"))
        self.assertEqual(len(files),5)
        for file in files:
            obj=json.loads(file.read_text())
            self.assertEqual(obj["$schema"],"https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(obj["type"],"object")

    def test_fat_requirements_explicitly_not_tested(self):
        from framework.validation.requirements import check_requirements
        result=check_requirements(ROOT)
        self.assertEqual(len(result["factory_requirements"]),3)
        self.assertTrue(all(x["fat_status"]=="NOT_TESTED" for x in result["factory_requirements"]))

    def test_false_fat_pass_is_rejected(self):
        from framework.validation.requirements import check_requirements
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for factory in ("lab-warehouse","lab-assembly","lab-packaging"):
                dest=root/"factories"/factory/"tests"
                dest.mkdir(parents=True)
                source=ROOT/"factories"/factory/"tests/requirements.json"
                dest.joinpath("requirements.json").write_text(source.read_text())
                (dest.parent/"factory.json").write_text((ROOT/"factories"/factory/"factory.json").read_text())
            bad=root/"factories/lab-warehouse/tests/requirements.json"
            obj=json.loads(bad.read_text())
            obj["fat_status"]="PASS"
            bad.write_text(json.dumps(obj))
            with self.assertRaises(FrameworkError):
                check_requirements(root)

    def test_new_architecture_ci_does_not_deploy(self):
        file=(ROOT/".github/workflows/architecture-qualification.yml").read_text()
        self.assertIn("pull_request",file)
        self.assertNotIn("self-hosted",file)
        self.assertNotIn("IGNITION_CONTROLLER_API_TOKEN",file)

    def test_cli_qualification(self):
        p=subprocess.run([sys.executable,"framework/cli/check_repo.py"],
                         cwd=ROOT,capture_output=True,text=True,timeout=25)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("STRUCTURE_VALIDATED_DEPLOYMENT_NOT_AUTHORIZED",p.stdout)

    def test_unmodified_native_mirrors(self):
        for factory,name in (("lab-warehouse","WarehouseHMI"),
                             ("lab-assembly","ConveyorHMI"),
                             ("lab-assembly","PackagingHMI")):
            self.assertEqual(
                (ROOT/"factories"/factory/"projects"/name/"project.json").read_bytes(),
                (ROOT/"ignition-project"/name/"project.json").read_bytes())

if __name__=="__main__":
    unittest.main()
