"""24-hour rolling start-window guard for independently AI-approved NBA C."""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from memarasix_nba_c import validate_nba_c

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)


def approval(start):
    return {
        "date": "2026-11-17",
        "approval_source": "chatgpt_ai_analyst",
        "approved_at_utc": NOW.isoformat(),
        "publication_allowed": True,
        "tickets": [{
            "id": "C",
            "analysis": "Statistika posljednjih utakmica, potvrđena granica, minutaža, rizici i kvalitet izvora su pregledani.",
            "matches": [
                {"player": "Example Player One", "player_id": "10001", "espn_event_id": "90001", "team": "Team A", "opponent": "Team B",
                 "start_utc": start.isoformat(), "market": "player_points", "pick": "over",
                 "points_line": 16.5, "odd": 1.81, "bookmaker": "Example Book", "source": "https://example.com/odds"},
                {"player": "Example Player Two", "player_id": "10002", "espn_event_id": "90001", "team": "Team A", "opponent": "Team B",
                 "start_utc": start.isoformat(), "market": "player_points", "pick": "under",
                 "points_line": 22.5, "odd": 1.83, "bookmaker": "Example Book", "source": "https://example.com/odds"}
            ]
        }]
    }


class Rolling24hTests(unittest.TestCase):
    def test_inside_next_24_hours_allowed(self):
        self.assertTrue(validate_nba_c(Path("."), approval(NOW + timedelta(hours=23, minutes=59)), NOW)["nba_c"])

    def test_later_than_24_hours_rejected(self):
        with self.assertRaisesRegex(ValueError, "24 hours"):
            validate_nba_c(Path("."), approval(NOW + timedelta(hours=24, minutes=1)), NOW)

    def test_started_or_within_20_minutes_rejected(self):
        for minutes in [-5, 0, 20]:
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                validate_nba_c(Path("."), approval(NOW + timedelta(minutes=minutes)), NOW)


if __name__ == "__main__":
    unittest.main()
