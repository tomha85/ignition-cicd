"""Connection inventory is configuration-only: validate without touching any OT system."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from framework.validation.connections import check_connections, check_factory_connections
from reusable_cicd.core import FrameworkError

ROOT = Path(__file__).resolve().parents[1]


class ConnectionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "factories", self.root / "factories")
        shutil.copytree(ROOT / "shared/schemas", self.root / "shared/schemas")
        self.factory = "lab-warehouse"

    def mutate(self, kind, records=None, **edits):
        key = {"gateways": "gateways", "databases": "databases",
               "opcua": "opcua_servers", "plc-devices": "plc_devices"}[kind]
        path = self.root / "factories" / self.factory / "connections" / (kind + ".json")
        data = json.loads(path.read_text())
        if records is not None:
            data[key] = records
            data["status"] = "DOCUMENTED_NOT_APPLIED" if records else "NOT_PROVIDED"
        data.update(edits)
        path.write_text(json.dumps(data) + "\n")
        return path

    def factory_gateway(self, **fields):
        return {"gateway_id": "warehouse-main", "environment": "test",
                "host": "gateway.example.invalid", "https_port": 8043,
                "source_reference": "CUSTOMER_GATEWAY_EXPORT_2026",
                "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED", **fields}

    def database(self, **fields):
        return {"name": "PlantHistorian", "gateway_id": "warehouse-main",
                "environment": "test", "driver": "postgresql",
                "host": "db-historian.example.invalid", "port": 5432,
                "database": "historian",
                "credential_ref": "FACTORY_A_HISTORIAN_DB",
                "source_reference": "CUSTOMER_DATABASE_CONFIG_2026",
                "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED", **fields}

    def opcua(self, **fields):
        return {"name": "ProductionOPC", "gateway_id": "warehouse-main",
                "environment": "test",
                "endpoint": "opc.tcp://opc.example.invalid:4840/UA/Server",
                "security_policy": "Basic256Sha256",
                "security_mode": "SignAndEncrypt",
                "certificate_ref": "FACTORY_A_OPC_CERT",
                "source_reference": "CUSTOMER_OPC_EXPORT_2026",
                "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED", **fields}

    def plc(self, **fields):
        return {"name": "PLC_001", "gateway_id": "warehouse-main",
                "environment": "test", "vendor": "Rockwell",
                "protocol": "ethernet-ip",
                "host": "plc-001.example.invalid", "port": 44818,
                "source_reference": "CUSTOMER_PLC_INVENTORY_2026",
                "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED", **fields}

    def test_all_factory_connection_templates_empty_not_invented(self):
        result = check_connections(ROOT)
        self.assertEqual(result["factory_count"], 3)
        self.assertEqual(result["connection_documents"], 12)
        self.assertEqual(result["declared_connections"], 0)
        self.assertEqual(result["database_runtime"], "NOT_TESTED")
        self.assertEqual(result["opcua_runtime"], "NOT_TESTED")
        self.assertEqual(result["plc_communications"], "NOT_TESTED")
        self.assertEqual(result["ignition_gateway_configuration"], "NOT_RUN")
        self.assertFalse(result["production_approved"])

    def test_realistic_source_documented_records_validate_as_metadata_only(self):
        for kind, record in (
            ("gateways", self.factory_gateway()),
            ("databases", self.database()),
            ("opcua", self.opcua()),
            ("plc-devices", self.plc()),
        ):
            self.mutate(kind, [record])
        result = check_connections(self.root)
        self.assertEqual(result["declared_connections"], 4)
        self.assertEqual(result["status"], "CONNECTION_METADATA_VALIDATED_NOT_APPLIED")
        self.assertFalse(result["production_approved"])

    def test_unverified_source_reference_blocked(self):
        self.mutate("databases", [self.database(source_reference="")])
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_wrong_factory_or_gateway_rejected(self):
        self.mutate("plc-devices", [self.plc(gateway_id="not-a-real-gateway")])
        with self.assertRaisesRegex(FrameworkError, "unregistered Gateway"):
            check_connections(self.root)
        self.mutate("plc-devices", [self.plc(gateway_id="assembly-main")])
        with self.assertRaisesRegex(FrameworkError, "unregistered Gateway"):
            check_connections(self.root)
        self.mutate("plc-devices", [self.plc()], factory_id="lab-packaging")
        with self.assertRaisesRegex(FrameworkError, "identity drift"):
            check_connections(self.root)

    def test_gateway_environment_not_registered(self):
        self.factory = "lab-assembly"
        self.mutate("gateways", [self.factory_gateway(
            gateway_id="utilities-main", environment="production")])
        with self.assertRaisesRegex(FrameworkError, "environment not declared"):
            check_connections(self.root)

    def test_literal_database_password_forbidden(self):
        self.mutate("databases", [self.database(password="DontCommitThis")])
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_database_connection_string_injection_rejected(self):
        self.mutate("databases", [self.database(connection_string="password=hunter2")])
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_secret_reference_must_be_name_not_secret(self):
        self.mutate("databases", [self.database(credential_ref="username:password")])
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_insecure_opc_ua_blocked(self):
        for bad in (
            {"security_mode": "None"},
            {"security_policy": "None"},
            {"endpoint": "opc.tcp://user:secret@opc.example.invalid:4840"},
            {"endpoint": "http://opc.example.invalid:4840"},
            {"endpoint": "opc.tcp://opc.example.invalid"},
            {"endpoint": "opc.tcp://opc.example.invalid:4840?token=abc"},
        ):
            with self.subTest(bad=bad):
                self.mutate("opcua", [self.opcua(**bad)])
                with self.assertRaises(FrameworkError):
                    check_connections(self.root)

    def test_bad_port_and_invalid_hostname_blocked(self):
        for kind, row in (
            ("gateways", self.factory_gateway(https_port=0)),
            ("databases", self.database(port=True)),
            ("plc-devices", self.plc(host="http://plc.example.invalid")),
        ):
            with self.subTest(kind=kind):
                self.mutate(kind, [row])
                with self.assertRaises(FrameworkError):
                    check_connections(self.root)
                self.mutate(kind, [])

    def test_no_declared_configuration_without_records(self):
        self.mutate("databases", [], status="DOCUMENTED_NOT_APPLIED")
        with self.assertRaisesRegex(FrameworkError, "status/count"):
            check_connections(self.root)
        self.mutate("databases", [self.database()], status="NOT_PROVIDED")
        with self.assertRaisesRegex(FrameworkError, "status/count"):
            check_connections(self.root)

    def test_automatic_connection_deployment_forbidden(self):
        self.mutate("plc-devices", [self.plc()], deployment_enabled=True)
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_fake_runtime_verified_or_connected_state_forbidden(self):
        self.mutate("opcua", [self.opcua(validation_state="CONNECTED")])
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_duplicate_gateway_name_per_environment_blocked(self):
        entry = self.database()
        self.mutate("databases", [entry, dict(entry)])
        with self.assertRaisesRegex(FrameworkError, "duplicate connection"):
            check_connections(self.root)

    def test_duplicate_json_key_and_symlink_blocked(self):
        file = self.mutate("databases")
        file.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(FrameworkError, "duplicate"):
            check_connections(self.root)
        self.mutate("databases", [])
        file.unlink()
        file.symlink_to(ROOT / "factories/lab-warehouse/connections/databases.json")
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_extra_unknown_connection_metadata_document_blocked(self):
        (self.root / "factories/lab-warehouse/connections/secret.json").write_text("{}")
        with self.assertRaisesRegex(FrameworkError, "unregistered"):
            check_connections(self.root)

    def test_hidden_env_and_private_key_files_block_repository(self):
        base = self.root / "factories/lab-warehouse/connections"
        for name in (".env", "client-private.key", "gateway-config.gwbk"):
            with self.subTest(name=name):
                path = base / name
                path.write_text("DUMMY_INVALID_CONTENT_NOT_A_SECRET")
                try:
                    with self.assertRaisesRegex(FrameworkError, "unregistered"):
                        check_connections(self.root)
                finally:
                    path.unlink()

    def test_connection_document_extra_fields_and_duplicate_identifiers_fail(self):
        self.mutate("gateways", [self.factory_gateway()])
        self.mutate("databases", [self.database()])
        self.mutate("opcua", [self.opcua()])
        self.mutate("plc-devices", [self.plc()])
        self.assertEqual(check_connections(self.root)["declared_connections"], 4)
        self.mutate("gateways", [self.factory_gateway(),
                                  self.factory_gateway()])
        with self.assertRaisesRegex(FrameworkError, "duplicate connection"):
            check_connections(self.root)
        self.mutate("gateways", [self.factory_gateway(unexpected_flag=True)])
        with self.assertRaises(FrameworkError):
            check_connections(self.root)

    def test_validator_never_contacts_gateway_or_plc(self):
        import framework.validation.connections as catalog
        self.assertNotIn("urlopen(", Path(catalog.__file__).read_text())
        self.assertNotIn("requests.", Path(catalog.__file__).read_text())
        self.assertNotIn("socket.connect", Path(catalog.__file__).read_text())
        self.assertNotIn("subprocess.run(", Path(catalog.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
