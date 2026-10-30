import sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cross_competition_history import select,standings_rows
class CrossCompetitionTests(unittest.TestCase):
    def test_standings_normalization(self):
        doc={"children":[{"standings":{"entries":[
            {"team":{"id":"12","displayName":"Bayer Leverkusen"},
             "stats":[{"name":"rank","value":2},{"name":"points","value":24}]}]}}]}
        rows=standings_rows(doc)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["team"],"Bayer Leverkusen")
        self.assertEqual(rows[0]["statistics"]["points"],24)
    def test_kickoff_and_standings_in_fixture(self):
        now=datetime(2026,10,30,tzinfo=timezone.utc)
        def request(url):
            if "/standings" in url:
                return {"standings":{"entries":[
                    {"team":{"id":"1","displayName":"Arsenal"},"stats":[{"name":"rank","value":1}]},
                    {"team":{"id":"2","displayName":"Chelsea"},"stats":[{"name":"rank","value":2}]}]}}
            return {"events":[]}
        feed={"football_candidates":[{"id":"fixture","sport":"football","status":"pre",
            "league":"eng.1","home":"Arsenal","away":"Chelsea",
            "start_utc":"2026-10-31T15:00:00Z","start_sarajevo":"2026-10-31T16:00:00+01:00"}]}
        result=select(feed,request=request,days=1,leagues=("eng.1",),now=now)
        fixture=result["fixtures"][0]
        self.assertEqual(fixture["start_utc"],"2026-10-31T15:00:00Z")
        self.assertEqual(fixture["home_standing"]["statistics"]["rank"],1)
        self.assertEqual(len(result["league_standings"]["eng.1"]),2)
    def test_cross_league_and_h2h(self):
        now=datetime(2026,10,30,tzinfo=timezone.utc)
        def request(url):
            if "/summary?" in url:return {"header":{"id":"ok"}}
            league=url.split("/soccer/")[1].split("/")[0]
            date=url.split("dates=")[1][:8]
            if date!="20261029":return {"events":[]}
            a,b=("Arsenal","Chelsea") if league=="eng.1" else ("Arsenal","Other")
            return {"events":[{"id":league,"date":"2026-10-29T15:00:00Z","status":{"type":{"state":"post"}},"competitions":[{"competitors":[{"team":{"displayName":a}},{"team":{"displayName":b}}]}]}]}
        feed={"football_candidates":[{"id":"new","sport":"football","status":"pre","league":"eng.1","home":"Arsenal","away":"Chelsea"}]}
        result=select(feed,request=request,days=2,leagues=("eng.1","uefa.champions"),now=now)
        x=result["fixtures"][0]
        self.assertEqual(len(x["home_history"]),2)
        self.assertEqual(len(x["away_history"]),1)
        self.assertEqual(len(x["h2h"]),1)
        self.assertFalse(result["publication_allowed"])
if __name__=="__main__":unittest.main()
