import json
import tempfile
import unittest
from pathlib import Path
from reset_daily_approvals import reset

class MidnightApprovalTests(unittest.TestCase):
    def test_old_approval_cleared_without_touching_bank_or_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for path in ("memarasix-football-ai-approved.json","memarasix-1455-approved.json"):
                (root/path).write_text(json.dumps({"date":"2026-11-22","tickets":[{"id":"A"}],"publication_allowed":True}))
            (root/"data.json").write_text('{"date":"2026-11-22","settled":false,"tickets":[{"id":"A"}]}')
            (root/"archive.json").write_text('[{"date":"2026-11-21"}]')
            self.assertEqual(len(reset(root,"2026-11-23")),2)
            self.assertEqual(reset(root,"2026-11-23"),[])
            self.assertFalse(json.loads((root/"memarasix-football-ai-approved.json").read_text())["publication_allowed"])
            self.assertIn('"settled":false',(root/"data.json").read_text())
            self.assertIn("2026-11-21",(root/"archive.json").read_text())

    def test_current_day_approval_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            p=root/"memarasix-football-ai-approved.json"
            p.write_text(json.dumps({"date":"2026-11-23","tickets":[{"id":"B"}]}))
            self.assertEqual(reset(root,"2026-11-23"),[])
            self.assertEqual(json.loads(p.read_text())["tickets"][0]["id"],"B")

if __name__=="__main__":
    unittest.main()
