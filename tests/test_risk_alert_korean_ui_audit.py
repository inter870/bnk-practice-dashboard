from __future__ import annotations

import unittest

from scripts.check_risk_alert_korean_ui import main


class RiskAlertKoreanUiAuditTests(unittest.TestCase):
    def test_risk_alert_korean_ui_audit_passes(self) -> None:
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
