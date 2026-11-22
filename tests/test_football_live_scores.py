import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from football_identity import identity
from sync_live_scores import run, extract


class FootballLiveScoreTests(unittest.TestCase):
    def test_fixture_identity_from_published_ai_ticket(self):
        match={"fixture_id":"espn:football:tur.1:401888248",
               "match":"Kasimpasa - Alanyaspor","datetime":"2026-11-22T13:00:00Z","pick":"1"}
        self.assertEqual(identity(match),("Kasimpasa","Alanyaspor","tur.1","401888248"))
        self.assertEqual(identity({"home":"A","away":"B","sport":"basketball"}),("A","B",None,None))

    def test_match_real_espn_event_id_without_explicit_home_away(self):
        day=datetime.now(timezone.utc).date().isoformat()
        kickoff=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        ticket={"date":day,"tickets":[{"id":"A","matches":[{
            "fixture_id":"espn:football:tur.1:401888248",
            "match":"Kasimpasa - Alanyaspor",
            "datetime":kickoff,"pick":"1"}]}]}
        event={"id":"401888248","date":kickoff,
               "status":{"type":{"state":"in","completed":False,"shortDetail":"54'"},"displayClock":"54:00"},
               "competitions":[{"competitors":[
                   {"homeAway":"home","score":"2","team":{"displayName":"Kasimpasa"}},
                   {"homeAway":"away","score":"1","team":{"displayName":"Alanyaspor"}}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            input_path=Path(tmp)/"data.json"
            output_path=Path(tmp)/"live.json"
            input_path.write_text(json.dumps(ticket),encoding="utf-8")
            with patch("sync_live_scores.fetch",return_value=[event]) as fetched:
                run(str(input_path),str(output_path))
            self.assertEqual(fetched.call_args.args[0],"tur.1")
            rows=json.loads(output_path.read_text())["matches"]
            self.assertEqual(rows[0]["state"],"live")
            self.assertEqual(rows[0]["score"],"2:1")
            self.assertEqual(rows[0]["event_id"],"401888248")
            self.assertEqual(rows[0]["minute"],"54")

    def test_wrong_fixture_id_stays_unverified(self):
        now=datetime.now(timezone.utc)
        kickoff=now.replace(microsecond=0).isoformat()
        ticket={"date":now.date().isoformat(),"tickets":[{"id":"B","matches":[{
            "fixture_id":"espn:football:ger.1:777",
            "match":"Alpha - Beta","datetime":kickoff,"pick":"3+"}]}]}
        event={"id":"778","date":kickoff,
               "status":{"type":{"state":"in","completed":False}},
               "competitions":[{"competitors":[
                   {"homeAway":"home","score":"2","team":{"displayName":"Alpha"}},
                   {"homeAway":"away","score":"1","team":{"displayName":"Beta"}}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            inp=Path(tmp)/"data.json"
            out=Path(tmp)/"live.json"
            inp.write_text(json.dumps(ticket),encoding="utf-8")
            with patch("sync_live_scores.fetch",return_value=[event]):
                run(str(inp),str(out))
            row=json.loads(out.read_text())["matches"][0]
            self.assertEqual(row["state"],"unverified")


if __name__=="__main__":
    unittest.main()
