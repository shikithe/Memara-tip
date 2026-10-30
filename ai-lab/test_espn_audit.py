import unittest
from datetime import date
from unittest.mock import patch
import espn_audit

class AuditTests(unittest.TestCase):
    def test_stat_keys(self):
        self.assertIn("expectedgoals",espn_audit.stat_names({"name":"expectedGoals"}))

    def test_sample(self):
        event={"id":"42","name":"Home - Away","status":{"type":{"state":"post"}}}
        def fake(url):
            if "scoreboard" in url:
                return {"events":[event]}
            return {"boxscore":{"teams":[{"statistics":[{"name":"shots"},{"name":"possession"}]}]},"rosters":[{"roster":[]}]}
        with patch.object(espn_audit,"fetch",side_effect=fake):
            result=espn_audit.audit_league("eng.1",date(2026,10,30),1,0)
        self.assertEqual(result["summary_success"],1)
        self.assertEqual(result["shots"],1)
        self.assertEqual(result["possession"],1)
        self.assertEqual(result["xg"],0)

if __name__=="__main__":
    unittest.main()
