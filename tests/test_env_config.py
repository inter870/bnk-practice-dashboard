from __future__ import annotations

import os
import unittest

from src.config.env import get_dart_api_key, get_ecos_api_key, mask_secret, sanitize_secret_text


class EnvConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old = {
            key: os.environ.get(key)
            for key in [
                "DART_API_KEY",
                "OPENDART_API_KEY",
                "OPEN_DART_API_KEY",
                "ECOS_API_KEY",
                "ECOS_AUTH_KEY",
                "BOK_ECOS_API_KEY",
                "BANK_OF_KOREA_API_KEY",
            ]
        }

    def tearDown(self) -> None:
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_dart_alias_prefers_existing_environment(self) -> None:
        os.environ["DART_API_KEY"] = "unit-dart-secret"
        os.environ["OPENDART_API_KEY"] = "unit-opendart-secret"
        self.assertEqual("unit-dart-secret", get_dart_api_key())

    def test_ecos_alias_reads_environment(self) -> None:
        os.environ.pop("ECOS_API_KEY", None)
        os.environ["ECOS_AUTH_KEY"] = "unit-ecos-secret"
        self.assertEqual("unit-ecos-secret", get_ecos_api_key())
        os.environ.pop("ECOS_AUTH_KEY", None)

    def test_mask_and_sanitize_do_not_expose_secret(self) -> None:
        secret = "abcdef1234567890"
        os.environ["DART_API_KEY"] = secret
        masked = mask_secret(secret)
        self.assertNotEqual(secret, masked)
        self.assertNotIn("345678", masked)
        message = sanitize_secret_text(f"failed url contains {secret}")
        self.assertNotIn(secret, message)
        self.assertIn(masked, message)


if __name__ == "__main__":
    unittest.main()
