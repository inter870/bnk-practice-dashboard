from __future__ import annotations

import unittest

from scripts.check_data_trust_display import _sample_html, audit_data_trust_html


class DataTrustDisplayAuditTests(unittest.TestCase):
    def test_generated_data_trust_html_has_no_bad_status_fragments(self) -> None:
        failures = audit_data_trust_html(_sample_html())
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
