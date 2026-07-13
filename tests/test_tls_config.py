import unittest
from unittest.mock import patch

from src.config.tls import configure_requests_ca_bundle


class TLSConfigTests(unittest.TestCase):
    def test_deployment_ca_bundle_is_preserved(self):
        environ = {"REQUESTS_CA_BUNDLE": "deployment-ca.pem"}

        with patch("src.config.tls.build_windows_ca_bundle") as builder:
            selected = configure_requests_ca_bundle("explicit-ca.pem", environ)

        self.assertEqual("deployment-ca.pem", selected)
        self.assertEqual("deployment-ca.pem", environ["REQUESTS_CA_BUNDLE"])
        builder.assert_not_called()

    def test_explicit_ca_bundle_precedes_windows_fallback(self):
        environ = {}

        with patch("src.config.tls.build_windows_ca_bundle") as builder:
            selected = configure_requests_ca_bundle("explicit-ca.pem", environ)

        self.assertEqual("explicit-ca.pem", selected)
        self.assertEqual("explicit-ca.pem", environ["REQUESTS_CA_BUNDLE"])
        builder.assert_not_called()

    def test_windows_bundle_is_used_only_as_fallback(self):
        environ = {}

        with patch("src.config.tls.build_windows_ca_bundle", return_value="windows-ca.pem"):
            selected = configure_requests_ca_bundle(None, environ)

        self.assertEqual("windows-ca.pem", selected)
        self.assertEqual("windows-ca.pem", environ["REQUESTS_CA_BUNDLE"])


if __name__ == "__main__":
    unittest.main()
