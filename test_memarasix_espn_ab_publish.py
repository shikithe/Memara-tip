import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from memarasix_espn_ab_publish import verify, publish, write, read

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
DAY = NOW.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
STAMP = "2026-11-21T09:30:00+00:00"
FEED = {
    "date": DAY, "generated_at_utc": STAMP,
    "expires_at_utc": "2026-11-22T08:00:00+00:00",
    "football_candidates": [
        {"fixture_id":"espn:football:ger.1:1","home":"Alpha","away":"Beta",
         "league":"ger.1","start_utc":"2026-11-21T15:00:00Z"},
        {"fixture_id":"espn:football:eng.1:2","home":"Gamma","away":"Delta",
         "league":"eng.1","start_utc":"2026-11-21T16:00:00Z"},
    ],
}
A = {"id":"A","analysis":"Full independent AI scouting of this fixture, its risk and recent form.",
     "matches":[{"fixture_id":"espn:football:ger.1:1","pick":"1","odd":2.1,
                 "bookmaker":"Public price reference","source":"https://example.org/quote",
                 "quote_checked_at_utc":"2026-11-21T09:55:00Z"}]}
B = {"id":"B","analysis":"Detailed independent AI scouting of total goals and match context.",
     "matches":[{"fixture_id":"espn:football:eng.1:2","pick":"3+","odd":2.3,
                 "bookmaker":"Public price reference","source":"https://example.org/quote2",
                 "quote_checked_at_utc":"2026-11-21T09:55:00Z"}]}
APPROVAL = {"date":DAY,"feed_generated_at_utc":STAMP,
            "approval_source":"chatgpt_ai_analyst",
            "publication_allowed":True,
            "approved_at_utc":"2026-11-21T09:56:00Z","tickets":[A,B]}
CURRENT = {"date":"2026-11-20","settled":True,"bank_after":200.0,
           "tickets":[{"id":"C","stake":2.0,"status":"objavljen"}]}

class ESPNABTests(unittest.TestCase):
    def test_two_tickets_without_kvoter(self):
        self.assertEqual([t["id"] for t in verify(APPROVAL, FEED, CURRENT, NOW)],["A","B"])

    def test_no_espn_identification_or_odds_validation(self):
        altered = copy.deepcopy(APPROVAL)
        altered["feed_generated_at_utc"] = "OLD"
        altered["tickets"][0]["matches"][0]["fixture_id"] = "AI-OWN-IDENTIFIER"
        altered["tickets"][0]["matches"][0]["odd"] = 2.34
        altered["tickets"][1]["matches"][0]["pick"] = "1"
        altered["tickets"][1]["matches"][0]["source"] = ""
        result = verify(altered, {}, CURRENT, NOW)
        self.assertEqual(result, altered["tickets"])

    def test_old_approval_date_is_rejected(self):
        altered = copy.deepcopy(APPROVAL)
        altered["date"] = "2026-11-20"
        with self.assertRaisesRegex(ValueError, "today"):
            verify(altered, None, CURRENT, NOW)

    def test_preserve_nba_c_and_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data={"date":DAY,"settled":False,"bank_before":200.0,
                  "bank_after":198.0,"tickets":[{"id":"C","stake":2.0,"status":"objavljen"}]}
            write(root/"data.json",data)
            write(root/"memarasix-football-ai-approved.json",APPROVAL)
            result=publish(root,NOW,FEED)
            self.assertEqual(result["status"],"published")
            after=read(root/"data.json")
            self.assertEqual({t["id"] for t in after["tickets"]},{"A","B","C"})
            self.assertEqual(next(t for t in after["tickets"] if t["id"]=="C"),data["tickets"][0])
            self.assertEqual(publish(root,NOW,FEED)["status"],"no_update")
            self.assertEqual(read(root/"data.json"),after)

    def test_unsettled_previous_day_fails_without_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            before={"date":"2026-11-20","settled":False,"bank_after":200,"tickets":[]}
            write(root/"data.json",before)
            write(root/"memarasix-football-ai-approved.json",APPROVAL)
            with self.assertRaisesRegex(ValueError,"settled"):
                publish(root,NOW,FEED)
            self.assertEqual(read(root/"data.json"),before)

if __name__ == "__main__":
    unittest.main()
