"""Ensure a depleted Odds API key does not trigger eight useless player-prop requests."""
import unittest
from unittest.mock import patch
from sync_nba_points import fetch


class FakeResponse:
    headers = {"x-requests-remaining": "0"}
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def read(self):
        return b'[]'


class NBAQuotaGuardTests(unittest.TestCase):
    def test_zero_credits_stops_before_markets(self):
        with patch("sync_nba_points.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "ODDS_API_QUOTA_EXHAUSTED"):
                fetch("https://api.the-odds-api.com/v4/sports/basketball_nba/events?apiKey=test", "test")

    def test_other_endpoints_do_not_use_free_events_guard(self):
        with patch("sync_nba_points.urlopen", return_value=FakeResponse()):
            result=fetch("https://api.the-odds-api.com/v4/sports/basketball_nba/events/123/odds?apiKey=test", "test")
            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
