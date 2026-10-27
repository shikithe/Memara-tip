import unittest
from datetime import datetime, timezone, timedelta
from nba_ticket_test import build

NOW = datetime(2026,10,27,16,0,tzinfo=timezone.utc)
def offer(player):
    return {"player":player,"game":"Test A vs Test B","side":"OVER",
            "line":20.5,"odds":1.8,"bookmaker":"Example",
            "source_url":"https://example.com/test",
            "snapshot_utc":(NOW-timedelta(minutes=10)).isoformat(),
            "start_utc":(NOW+timedelta(hours=6)).isoformat(),
            "status":"verified"}
class TicketTests(unittest.TestCase):
    def test_two_unique_players(self):
        r=build({"offers":[offer("A"),offer("A"),offer("B")]},NOW)
        self.assertEqual(r["status"],"complete")
        self.assertEqual(r["combined_odds"],3.24)
        self.assertFalse(r["publication_allowed"])
    def test_stale_rejected(self):
        a=offer("A");a["snapshot_utc"]=(NOW-timedelta(hours=4)).isoformat()
        self.assertEqual(build({"offers":[a,offer("B")]},NOW)["status"],"insufficient_verified_offers")
    def test_unverified_rejected(self):
        a=offer("A");a["status"]="unverified"
        self.assertEqual(build({"offers":[a,offer("B")]},NOW)["status"],"insufficient_verified_offers")
if __name__=="__main__":
    unittest.main()
