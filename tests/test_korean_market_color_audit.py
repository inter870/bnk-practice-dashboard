from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_korean_market_colors.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("check_korean_market_colors", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Korean market color audit script.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KoreanMarketColorAuditTests(unittest.TestCase):
    def test_korean_market_color_audit_passes(self) -> None:
        module = _load_audit_module()
        self.assertEqual([], module.audit_files())


if __name__ == "__main__":
    unittest.main()
