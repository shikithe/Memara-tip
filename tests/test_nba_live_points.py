import unittest
from datetime import datetime, timezone
from nba_live_points import enrich,player_points,read_state

def sample(points=26,state="in",completed=False):
    return {"header":{"competitions":[{"status":{"type":{"state":state,"completed":completed},"displayClock":"6:50","period":3}}]},
            "boxscore":{"players":[{"statistics":[{"keys":["minutes","points","rebounds"],"athletes":[{"athlete":{"id":"42"},"stats":["31",str(points),"5"]}]}]}]}}

class NBABoxscoreTests(unittest.TestCase):
    def test_strict_player_id(self):
        self.assertEqual(player_points(sample(),"42"),26)
        self.assertIsNone(player_points(sample(),"43"))
    def test_live_over_hit(self):
        m={"sport":"basketball","market":"player_points","pick":"over","points_line":25.5,"espn_event_id":"401","player_id":"42","start_utc":"2026-11-15T20:00:00Z","home":"A","away":"B"}
        published={"tickets":[{"id":"C","matches":[m]}]}
        records=[{"ticket":"C","index":0,"home":"A","away":"B","state":"unverified"}]
        output=enrich(published,records,{},datetime(2026,11,15,21,0,tzinfo=timezone.utc),lambda x:sample())
        self.assertEqual(output[0]["player_points"],26)
        self.assertEqual(output[0]["result_status"],"pogođen")
    def test_under_not_settled_early(self):
        m={"sport":"basketball","market":"player_points","pick":"under","points_line":25.5,"espn_event_id":"401","player_id":"42","start_utc":"2026-11-15T20:00:00Z","home":"A","away":"B"}
        published={"tickets":[{"id":"C","matches":[m]}]}
        records=[{"ticket":"C","index":0,"home":"A","away":"B","state":"unverified"}]
        output=enrich(published,records,{},datetime(2026,11,15,21,0,tzinfo=timezone.utc),lambda x:sample(12))
        self.assertNotIn("result_status",output[0])
    def test_dnp_only_after_final(self):
        m={"sport":"basketball","market":"player_points","pick":"over","points_line":25.5,"espn_event_id":"401","player_id":"42","start_utc":"2026-11-15T20:00:00Z","home":"A","away":"B"}
        published={"tickets":[{"id":"C","matches":[m]}]}
        def run(doc):
            return enrich(published,[{"ticket":"C","index":0,"home":"A","away":"B","state":"unverified"}],{},datetime(2026,11,15,22,0,tzinfo=timezone.utc),lambda x:doc)[0]
        d=sample(state="post",completed=True)
        d["boxscore"]["players"][0]["statistics"][0]["athletes"][0].update(didNotPlay=True,stats=[])
        got=run(d)
        self.assertTrue(got["void"])
        self.assertEqual(got["effective_odd"],1.0)
        self.assertEqual(got["result_status"],"pogođen")
        d["header"]["competitions"][0]["status"]["type"].update(state="in",completed=False)
        self.assertNotIn("void",run(d))

    def test_missing_player_only_when_both_final_boxscores_complete(self):
        m={"sport":"basketball","market":"player_points","pick":"over","points_line":23.5,"espn_event_id":"401","player_id":"42","start_utc":"2026-11-15T20:00:00Z","home":"A","away":"B"}
        published={"tickets":[{"id":"C","matches":[m]}]}
        entries=lambda start:[{"athlete":{"id":str(i)},"stats":["20","5"]} for i in range(start,start+8)]
        d=sample(state="post",completed=True)
        d["boxscore"]["players"]=[{"statistics":[{"keys":["minutes","points"],"athletes":entries(100)}]},{"statistics":[{"keys":["minutes","points"],"athletes":entries(200)}]}]
        def run(doc):
            return enrich(published,[{"ticket":"C","index":0,"home":"A","away":"B","state":"unverified"}],{},datetime(2026,11,15,22,0,tzinfo=timezone.utc),lambda x:doc)[0]
        self.assertTrue(run(d)["void"])
        d["boxscore"]["players"].pop()
        self.assertNotIn("void",run(d))

    def test_final(self):
        self.assertEqual(read_state(sample(state="post",completed=True))[0],"final")

if __name__=="__main__":unittest.main()
