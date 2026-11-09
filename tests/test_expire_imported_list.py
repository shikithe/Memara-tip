import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from memarasix_expire_imported_list import run

SAR = ZoneInfo("Europe/Sarajevo")
WHEN = datetime(2026, 11, 9, 8, 56, tzinfo=SAR)


def store(root, name, obj):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


class ExpireImportedTest(unittest.TestCase):
    def make_root(self, path, day="2026-11-08"):
        store(path,"listasix-data/active-list.json",{"date":day,"fixtures":[{"fixture_id":"abc"}]})
        store(path,"listasix-data/history-h2h.json",{"date":day})
        store(path,"listasix-data/sync-receipt.json",{"date":day})
        store(path,"data.json",{"date":day,"tickets":[{"id":"A"}],"bank_after":230.8})
        store(path,"memarasix-1455-approved.json",{"date":day,"tickets":[]})
        store(path,"archives/2026-11-08.json",{"date":day})

    def test_only_import_deleted_and_finances_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_root(root)
            self.assertTrue(run(root,WHEN,"2026-11-09"))
            for name in ("active-list","history-h2h","sync-receipt"):
                self.assertFalse((root/"listasix-data"/(name+".json")).exists())
            self.assertTrue((root/"data.json").exists())
            self.assertTrue((root/"memarasix-1455-approved.json").exists())
            self.assertTrue((root/"archives/2026-11-08.json").exists())
            ack=json.loads((root/"listasix-data/expiry-receipt.json").read_text())
            self.assertEqual(ack["date"],"2026-11-09")
            self.assertEqual(ack["status"],"expired_previous_day")

    def test_repeat_does_not_change_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_root(root)
            self.assertTrue(run(root,WHEN,"2026-11-09"))
            before=(root/"listasix-data/expiry-receipt.json").read_text()
            self.assertFalse(run(root,WHEN,"2026-11-09"))
            self.assertEqual((root/"listasix-data/expiry-receipt.json").read_text(),before)

    def test_dont_delete_new_day_import(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_root(root,"2026-11-09")
            self.assertTrue(run(root,WHEN,"2026-11-09"))
            self.assertTrue((root/"listasix-data/active-list.json").exists())
            self.assertEqual(json.loads((root/"listasix-data/expiry-receipt.json").read_text())["status"],"current_day_preserved")

    def test_never_before_0855(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_root(root)
            with self.assertRaisesRegex(ValueError,"08:55"):
                run(root,datetime(2026,11,9,8,54,tzinfo=SAR),"2026-11-09")
            self.assertTrue((root/"listasix-data/active-list.json").exists())

    def test_wrong_date_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_root(root)
            with self.assertRaisesRegex(ValueError,"date"):
                run(root,WHEN,"2026-11-08")
            self.assertTrue((root/"listasix-data/active-list.json").exists())

    def test_invalid_json_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_root(root)
            (root/"listasix-data/active-list.json").write_text("{broken")
            with self.assertRaisesRegex(ValueError,"Unreadable"):
                run(root,WHEN,"2026-11-09")
            self.assertTrue((root/"listasix-data/sync-receipt.json").exists())

    def test_no_active_stale_companions_removed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            store(root,"listasix-data/sync-receipt.json",{"date":"2026-11-08"})
            store(root,"listasix-data/history-h2h.json",{"date":"2026-11-08"})
            self.assertTrue(run(root,WHEN,"2026-11-09"))
            self.assertFalse((root/"listasix-data/sync-receipt.json").exists())
            self.assertFalse((root/"listasix-data/history-h2h.json").exists())

if __name__ == "__main__":
    unittest.main()
