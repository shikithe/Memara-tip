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

    def test_ab_only_cannot_consume_nba_c_reserve(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data={"date":DAY,"settled":True,"bank_before":200.0,
                  "bank_after":200.0,"tickets":[]}
            write(root/"data.json",data)
            write(root/"memarasix-football-ai-approved.json",APPROVAL)
            result=publish(root,NOW,FEED)
            self.assertEqual(result["status"],"published")
            after=read(root/"data.json")
            self.assertEqual(after["football_ab_budget"],17.0)
            self.assertEqual(after["reserved_nba_c_budget"],3.0)
            self.assertEqual(after["daily_budget"],20.0)
            self.assertEqual(after["daily_stake"],17.0)
            self.assertEqual(sum(x["stake"] for x in after["tickets"]),17.0)
            self.assertEqual(after["bank_after_stakes"],183.0)

    def test_existing_c_stake_cannot_be_overwritten_or_exceed_daily_ten_percent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c={"id":"C","stake":3.0,"status":"objavljen"}
            data={"date":DAY,"settled":False,"bank_before":200.0,
                  "bank_after":197.0,"tickets":[c]}
            write(root/"data.json",data)
            write(root/"memarasix-football-ai-approved.json",APPROVAL)
            result=publish(root,NOW,FEED)
            self.assertEqual(result["status"],"published")
            after=read(root/"data.json")
            self.assertEqual(after["tickets"][0],c)
            self.assertEqual(after["daily_stake"],20.0)
            self.assertEqual(after["football_ab_budget"],17.0)
            self.assertEqual(after["reserved_nba_c_budget"],3.0)
            self.assertEqual(after["bank_after"],180.0)
            self.assertEqual(publish(root,NOW,FEED)["status"],"no_update")

    def test_publish_A_and_B_independently_on_two_approval_pushes(self):
        # Ticket A is ready first; B is not a prerequisite. Later B is appended.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data={"date":DAY,"settled":True,"bank_before":200.0,
                  "bank_after":200.0,"tickets":[]}
            write(root/"data.json",data)
            first=copy.deepcopy(APPROVAL)
            first["tickets"]=[copy.deepcopy(A)]
            first["tickets"][0]["matches"].append(
                dict(first["tickets"][0]["matches"][0],
                     fixture_id="espn:football:ger.1:99"))
            write(root/"memarasix-football-ai-approved.json",first)
            out_a=publish(root,NOW,FEED)
            self.assertEqual(out_a["status"],"published")
            self.assertEqual(out_a["tickets"],["A"])
            after_a=read(root/"data.json")
            self.assertEqual([t["id"] for t in after_a["tickets"]],["A"])
            self.assertEqual(len(after_a["tickets"][0]["matches"]),2)
            self.assertAlmostEqual(after_a["tickets"][0]["stake"],12.28)
            a_saved=copy.deepcopy(after_a["tickets"][0])
            first_published_at=after_a["published_at_utc"]
            # The next approved file may contain only the new B ticket.
            second=copy.deepcopy(APPROVAL)
            second["approved_at_utc"]="2026-11-21T09:57:00+00:00"
            second["tickets"]=[copy.deepcopy(B)]
            second["tickets"][0]["matches"].append(
                dict(second["tickets"][0]["matches"][0],
                     fixture_id="espn:football:eng.1:99"))
            write(root/"memarasix-football-ai-approved.json",second)
            out_b=publish(root,NOW,FEED)
            self.assertEqual(out_b["status"],"published")
            self.assertEqual(out_b["tickets"],["B"])
            after_b=read(root/"data.json")
            self.assertEqual([t["id"] for t in after_b["tickets"]],["A","B"])
            self.assertEqual(after_b["tickets"][0],a_saved)
            self.assertEqual(after_b["published_at_utc"],first_published_at)
            self.assertEqual(len(after_b["tickets"][1]["matches"]),2)
            self.assertAlmostEqual(after_b["tickets"][1]["stake"],4.72)
            self.assertAlmostEqual(after_b["daily_stake"],17.0)
            self.assertAlmostEqual(after_b["reserved_nba_c_budget"],3.0)
            self.assertEqual(publish(root,NOW,FEED)["status"],"no_update")

    def test_stale_approval_does_not_publish_or_rewrite_today_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            current={"date":DAY,"settled":True,"bank_before":200.0,
                     "bank_after":200.0,"tickets":[]}
            stale=copy.deepcopy(APPROVAL)
            stale["date"]="2026-11-20"
            stale["approved_at_utc"]="2026-11-20T09:56:00Z"
            write(root/"data.json",current)
            write(root/"memarasix-football-ai-approved.json",stale)
            with self.assertRaisesRegex(ValueError,"not for today"):
                publish(root,NOW,FEED)
            self.assertEqual(read(root/"data.json"),current)

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
