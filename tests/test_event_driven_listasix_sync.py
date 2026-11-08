import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

from memarasix_sync_listasix import canonical_hash, validate, write_snapshot

NOW=datetime(2026,11,8,9,6,tzinfo=timezone.utc)


def inputs():
    a={"date":"2026-11-08","publication_allowed":True,
       "expires_at":"2026-11-09T08:59:00+01:00",
       "fixtures":[{"fixture_id":"espn:football:eng.1:123",
                    "match":"Arsenal - Chelsea","datetime":"2026-11-08T19:00:00Z"}]}
    h={"date":"2026-11-08","leagues":{"eng.1":{"teams":{}}},
       "fixtures":[{"fixture_id":"espn:football:eng.1:123"}]}
    return a,h


class EventSyncTests(unittest.TestCase):
    def test_valid_event_proves_same_list(self):
        a,h=inputs()
        hashvalue=canonical_hash(a)
        receipt=validate(a,h,NOW,expected_date="2026-11-08",expected_sha256=hashvalue)
        self.assertEqual(receipt["active_sha256"],hashvalue)
        self.assertEqual(receipt["fixtures"],1)

    def test_reject_different_snapshot_hash(self):
        a,h=inputs()
        with self.assertRaises(ValueError):
            validate(a,h,NOW,expected_date="2026-11-08",expected_sha256="0"*64)

    def test_reject_wrong_event_day(self):
        a,h=inputs()
        with self.assertRaises(ValueError):
            validate(a,h,NOW,expected_date="2026-11-07")

    def test_reject_history_yesterday(self):
        a,h=inputs()
        h["date"]="2026-11-07"
        with self.assertRaises(ValueError):
            validate(a,h,NOW)

    def test_reject_unapproved_or_expired(self):
        a,h=inputs()
        a["publication_allowed"]=False
        with self.assertRaises(ValueError):
            validate(a,h,NOW)
        a["publication_allowed"]=True
        a["expires_at"]="2026-11-08T06:00:00Z"
        with self.assertRaises(ValueError):
            validate(a,h,NOW)

    def test_reject_duplicates(self):
        a,h=inputs()
        a["fixtures"].append(a["fixtures"][0])
        with self.assertRaises(ValueError):
            validate(a,h,NOW)

    def test_save_three_artifacts_with_receipt_atomically(self):
        a,h=inputs()
        receipt=validate(a,h,NOW)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            write_snapshot(root,a,h,receipt)
            saved=json.loads((root/"listasix-data/active-list.json").read_text())
            ack=json.loads((root/"listasix-data/sync-receipt.json").read_text())
            hist=json.loads((root/"listasix-data/history-h2h.json").read_text())
            self.assertEqual(canonical_hash(saved),ack["active_sha256"])
            self.assertEqual(hist["date"],saved["date"])
            self.assertFalse(list((root/"listasix-data").glob("*.tmp")))


if __name__=="__main__":
    unittest.main()
