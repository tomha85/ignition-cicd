"""Network preflight tests are offline; never open a real network connection."""
import tempfile
import unittest
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.customer_plan import load_profile
from scripts.customer_network_preflight import probe

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config/example-company-multi-site.json"


class FakeSocket:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeTLSContext:
    def __init__(self):
        self.host = None

    def wrap_socket(self, raw, server_hostname):
        self.host = server_hostname
        return FakeSocket()


class CustomerNetworkPreflightTests(unittest.TestCase):
    def test_onprem_and_cloud_controllers_with_mocked_tls(self):
        profile = load_profile(PROFILE)
        for controller, expected_host in (
            ("hq-controller", "hq-eam.example.invalid"),
            ("regional-cloud-controller", "eam.private.example.invalid"),
        ):
            with self.subTest(controller=controller), \
                 tempfile.TemporaryDirectory() as directory:
                ca = Path(directory) / "root-ca.crt"
                ca.write_text("MOCKED-CA-FOR-TEST-ONLY")
                destination = []
                context = FakeTLSContext()

                def connector(addr, timeout):
                    destination.append((addr, timeout))
                    return FakeSocket()

                result = probe(
                    profile, controller, ca,
                    socket_opener=connector,
                    tls_context_factory=lambda cafile: context,
                )
                self.assertEqual(destination, [((expected_host, 8043), 5)])
                self.assertEqual(context.host, expected_host)
                self.assertEqual(result["status"], "TLS_HANDSHAKE_VERIFIED")
                self.assertEqual(result["eam_api_authorized"], "NOT_TESTED")
                self.assertEqual(result["eam_send_project"], "NOT_RUN")
                self.assertEqual(result["production"], "HOLD")

    def test_missing_ca_refused_even_with_mock_network(self):
        profile = load_profile(PROFILE)
        with self.assertRaisesRegex(FrameworkError, "CA file"):
            probe(profile, "hq-controller", Path("/missing/not-here"))

    def test_unknown_controller_refused(self):
        profile = load_profile(PROFILE)
        with tempfile.TemporaryDirectory() as directory:
            ca = Path(directory) / "ca.crt"
            ca.write_text("test")
            with self.assertRaisesRegex(FrameworkError, "unknown"):
                probe(profile, "wrong-controller", ca)

    def test_schema_v1_preflight_not_implicit(self):
        profile = load_profile(ROOT / "config/example-customer-testlab.json")
        with self.assertRaisesRegex(FrameworkError, "v2"):
            probe(profile, "none", Path("/missing"))


if __name__ == "__main__":
    unittest.main()
