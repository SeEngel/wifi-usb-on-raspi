#!/usr/bin/env python3
"""Unit tests for the rule-matching logic in wirehublib (no sysfs needed)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import wirehublib as lib


def rule(**kw):
    r = {"name": "test", "vid": None, "pid": None, "serial": None, "autoExport": True}
    r.update(kw)
    return r


DEV = {"busid": "1-1.4", "vid": "0781", "pid": "5567", "serial": "XYZ123",
       "product": "Ultra", "manufacturer": "SanDisk"}


class TestMatches(unittest.TestCase):
    def test_match_all_fields(self):
        self.assertTrue(lib.matches(rule(vid="0781", pid="5567"), DEV))

    def test_rd_mismatch(self):
        self.assertFalse(lib.matches(rule(vid="abcd"), DEV))

    def test_serial_wildcard(self):
        self.assertTrue(lib.matches(rule(vid="0781", pid="5567", serial=None), DEV))

    def test_serial_mismatch(self):
        self.assertFalse(lib.matches(rule(vid="0781", pid="5567", serial="other"), DEV))

    def test_match_everything_is_also_a_match(self):
        self.assertTrue(lib.matches(rule(), DEV))


class TestLoadConfig(unittest.TestCase):
    def _tmpcfg(self, raw):
        p = Path(tempfile.mkdtemp()) / "cfg.json"
        p.write_text(raw)
        return str(p)

    def test_normalizes_and_validates(self):
        cfg = lib.load_config(self._tmpcfg(json.dumps({"allowlist": [
            {"name": "s", "vid": "0781", "pid": "5567", "serial": ""}
        ]})))
        self.assertEqual(cfg["allowlist"][0]["vid"], "0781")
        self.assertEqual(cfg["allowlist"][0]["pid"], "5567")
        self.assertEqual(cfg["allowlist"][0]["serial"], None)

    def test_empty_allowlist_ok(self):
        cfg = lib.load_config(self._tmpcfg(json.dumps({"allowlist": []})))
        self.assertEqual(cfg["allowlist"], [])


if __name__ == "__main__":
    unittest.main()
