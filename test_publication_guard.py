import unittest
from datetime import datetime, timezone
from publication_guard import validate, allocate
NOW=datetime(2026,10,27,12,tzinfo=timezone.utc)
FEED={"date":"2026-10-27","football_candidates":[{"id":"e1","start_utc":"2026-10-27T19:00:00Z","status":"pre"}]}
LEG={"fixture_id":"e1","bookmaker":"bet365","odds":1.85,"odds_verified_at_utc":"2026-10-27T11:30:00Z"}
class TestPublicationGuard(unittest.TestCase):
    def test_valid(self): self.assertEqual(len(validate(FEED,[{"id":"A","matches":[LEG]}],NOW)),1)
    def test_missing_odds(self):
        with self.assertRaises(ValueError): validate(FEED,[{"id":"A","matches":[dict(LEG,bookmaker=None)]}],NOW)
    def test_duplicate(self):
        with self.assertRaises(ValueError): validate(FEED,[{"id":"A","matches":[LEG]},{"id":"B","matches":[LEG]}],NOW)
    def test_bank(self): self.assertLessEqual(sum(allocate(182.59,["A","B","C"]).values()),18.26)
    def test_ab(self): self.assertEqual(allocate(100,["A","B"]),{"A":7.0,"B":3.0})
    def test_stale(self):
        with self.assertRaises(ValueError): validate(FEED,[{"id":"A","matches":[dict(LEG,odds_verified_at_utc="2026-10-27T08:00:00Z")]}],NOW)
if __name__=="__main__": unittest.main()
