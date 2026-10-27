import unittest
from nba_stats_collector import parse,select

class NBAStatsTests(unittest.TestCase):
    def test_regular_plus_preseason(self):
        events={str(i):{"gameDate":f"2026-10-{20+i:02d}T00:00Z","opponent":{"abbreviation":"BOS"}} for i in range(1,6)}
        payload={"labels":["MIN","PTS"],"events":events,"seasonTypes":[
          {"displayName":"Regular Season","categories":[{"events":[{"eventId":str(i),"stats":["30",str(i*10)]} for i in (4,5)]}]},
          {"displayName":"Preseason","categories":[{"events":[{"eventId":str(i),"stats":["20",str(i*10)]} for i in (1,2,3)]}]}]}
        result=select(parse(payload))
        self.assertEqual((result["regular_count"],result["preseason_count"]),(2,3))
        self.assertEqual(result["weighted_avg_points"],34.29)
        self.assertTrue(result["complete_five"])
    def test_excludes_dnp(self):
        payload={"labels":["MIN","PTS"],"events":{"1":{"gameDate":"2026-10-21"}},"seasonTypes":[{"displayName":"Regular Season","categories":[{"events":[{"eventId":"1","stats":["0","0"]}]}]}]}
        self.assertEqual(parse(payload),[])
        self.assertFalse(select(parse(payload))["complete_five"])
if __name__=="__main__":unittest.main()
