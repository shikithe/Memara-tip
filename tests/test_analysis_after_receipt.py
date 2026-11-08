"""Test ready-list-triggered approval and late-publication safety gates."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from memarasix_1455_publish import (
    publication_clock_allowed, valid_ready_receipt, digest_active
)

SAR=ZoneInfo("Europe/Sarajevo")

def clock(hour,minute):
    return datetime(2026,11,8,hour,minute,tzinfo=SAR)


class ReadyListAnalysisGateTests(unittest.TestCase):
    def test_normal_publication_window_is_unchanged(self):
        self.assertFalse(publication_clock_allowed(clock(11,59)))
        self.assertTrue(publication_clock_allowed(clock(12,0)))
        self.assertTrue(publication_clock_allowed(clock(12,30)))
        self.assertFalse(publication_clock_allowed(clock(12,31)))
        self.assertFalse(publication_clock_allowed(clock(20,10)))

    def test_late_only_with_explicit_ready_event(self):
        self.assertFalse(publication_clock_allowed(clock(11,0),True))
        self.assertTrue(publication_clock_allowed(clock(12,31),True))
        self.assertTrue(publication_clock_allowed(clock(20,10),True))
        self.assertFalse(publication_clock_allowed(clock(23,0),True))

    def test_late_requires_same_day_exact_copy_and_ack(self):
        active={"date":"2026-11-08","publication_allowed":True,
                "fixtures":[{"fixture_id":"espn:football:eng.1:4010"}]}
        receipt={"date":"2026-11-08","active_sha256":digest_active(active)}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"listasix-data").mkdir()
            (root/"listasix-data/sync-receipt.json").write_text(json.dumps(receipt))
            (root/"listasix-data/active-list.json").write_text(json.dumps(active))
            self.assertTrue(valid_ready_receipt(root,"2026-11-08",active))
            self.assertFalse(valid_ready_receipt(root,"2026-11-09",active))
            changed=json.loads(json.dumps(active))
            changed["fixtures"].append({"fixture_id":"espn:football:eng.1:4011"})
            self.assertFalse(valid_ready_receipt(root,"2026-11-08",changed))

    def test_late_rejects_missing_or_corrupt_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertFalse(valid_ready_receipt(root,"2026-11-08",{}))
            path=root/"listasix-data"
            path.mkdir()
            (path/"sync-receipt.json").write_text("bad json")
            self.assertFalse(valid_ready_receipt(root,"2026-11-08",{}))


if __name__=="__main__":
    unittest.main()
