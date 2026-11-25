#!/usr/bin/env python3
"""Isolated integration test: real C validation and publishing functions, synthetic offers.

No live approval, data.json, bank or archive is modified. Every test works
in a tempfile; any player IDs, games and prices are deliberately fictional.
This proves only technical pipeline behavior, NOT quality of real AI Scout.
"""
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from memarasix_approval_gate import check_files
from memarasix_1455_publish import publish_nba_c

SAR = ZoneInfo("Europe/Sarajevo")


@contextmanager
def sandbox():
    with tempfile.TemporaryDirectory(prefix="memara-c-dryrun-") as directory:
        prior = os.getcwd()
        os.chdir(directory)
        try:
            yield Path(directory)
        finally:
            os.chdir(prior)


def write(root, name, data):
    (root / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fixture(now, late_minutes=120):
    day = now.astimezone(SAR).date().isoformat()
    start = (now + timedelta(minutes=late_minutes)).isoformat()
    return {
      "date": day,
      "approval_source": "chatgpt_ai_analyst",
      "approved_at_utc": now.isoformat(),
      "publication_allowed": True,
      "state": "nba_c_ai_manual_approved_for_technical_publishing",
      "tickets": [{
        "id": "C",
        "analysis": "Testni primjeri, namjerno izmišljeni; ovaj tekst ne predstavlja stvarnu sportsku analizu ili odobrenje.",
        "scout_analysis": {"date": day, "intro": "Sintetički test", "players": [], "conclusion": "Test", "caution": "Nije stvarna analiza"},
        "matches": [
          {"player_id": "TEST-P1", "player": "SYNTHETIC PLAYER ONE",
           "espn_event_id": "TEST-E1", "team": "TEST-HOME", "opponent": "TEST-AWAY",
           "start_utc": start, "market": "player_points", "pick": "over",
           "points_line": 21.5, "odd": 1.82, "bookmaker": "TEST-ONLY",
           "source": "https://example.org/test-quote-one", "quote_timestamp_verified": False},
          {"player_id": "TEST-P2", "player": "SYNTHETIC PLAYER TWO",
           "espn_event_id": "TEST-E2", "team": "TEST-HOME2", "opponent": "TEST-AWAY2",
           "start_utc": start, "market": "player_points", "pick": "under",
           "points_line": 18.5, "odd": 1.87, "bookmaker": "TEST-ONLY",
           "source": "https://example.org/test-quote-two", "quote_timestamp_verified": False}
        ]
      }]
    }


def ledger(now, stake_b=7.5):
    day = now.astimezone(SAR).date().isoformat()
    return {"date": day, "bank_before": 317.70,
            "bank_after": round(317.70 - 19.5 - stake_b, 2),
            "daily_budget": 31.77, "daily_stake": round(19.5 + stake_b, 2),
            "tickets": [{"id": "A", "stake": 19.5, "status": "objavljen"},
                        {"id": "B", "stake": stake_b, "status": "objavljen"}],
            "settled": False, "pending_ticket_statuses": {"A": "objavljen", "B": "objavljen"}}


class TicketCEndToEndDryRun(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)

    def test_01_fresh_input_to_verified_gate_to_published_only_in_sandbox(self):
        with sandbox() as root:
            write(root, "data.json", ledger(self.now))
            write(root, "memarasix-1455-approved.json", fixture(self.now))
            write(root, "archive.json", [{"immutable": True}])
            checked = check_files(root, self.now)
            self.assertTrue(checked["nba_c"])
            self.assertEqual(len(checked["verified_matches"]), 2)
            with patch("memarasix_1455_publish.ROOT", root):
                publish_nba_c(checked, self.now, self.now.astimezone(SAR))
            result = json.loads((root / "data.json").read_text())
            audit = json.loads((root / "memarasix-1455-audit.json").read_text())
            self.assertEqual(audit["status"], "published")
            self.assertEqual([x["id"] for x in result["tickets"]], ["A", "B", "C"])
            self.assertEqual(result["tickets"][2]["stake"], 4.77)
            self.assertEqual(result["bank_after"], 285.93)
            self.assertEqual(result["tickets"][2]["matches"][0]["points_line"], 21.5)
            self.assertEqual(json.loads((root / "archive.json").read_text()), [{"immutable": True}])

    def test_02_second_publish_does_not_charge_again(self):
        with sandbox() as root:
            write(root, "data.json", ledger(self.now))
            write(root, "memarasix-1455-approved.json", fixture(self.now))
            checked = check_files(root, self.now)
            with patch("memarasix_1455_publish.ROOT", root):
                publish_nba_c(checked, self.now, self.now.astimezone(SAR))
                before = json.loads((root / "data.json").read_text())
                publish_nba_c(checked, self.now, self.now.astimezone(SAR))
                after = json.loads((root / "data.json").read_text())
                audit = json.loads((root / "memarasix-1455-audit.json").read_text())
            self.assertEqual(before, after)
            self.assertEqual(audit["status"], "blocked")

    def test_03_stale_approval_rejected(self):
        with sandbox() as root:
            approved = fixture(self.now)
            approved["date"] = (self.now.astimezone(SAR).date() - timedelta(days=1)).isoformat()
            write(root, "memarasix-1455-approved.json", approved)
            with self.assertRaisesRegex(ValueError, "dated today"):
                check_files(root, self.now)

    def test_04_started_soon_rejected(self):
        with sandbox() as root:
            write(root, "memarasix-1455-approved.json", fixture(self.now, late_minutes=10))
            with self.assertRaisesRegex(ValueError, "too close"):
                check_files(root, self.now)

    def test_05_missing_budget_blocks_without_changing_ledger(self):
        with sandbox() as root:
            existing = ledger(self.now, stake_b=11.0)
            write(root, "data.json", existing)
            write(root, "memarasix-1455-approved.json", fixture(self.now))
            checked = check_files(root, self.now)
            with patch("memarasix_1455_publish.ROOT", root):
                publish_nba_c(checked, self.now, self.now.astimezone(SAR))
            after = json.loads((root / "data.json").read_text())
            audit = json.loads((root / "memarasix-1455-audit.json").read_text())
            self.assertEqual(after, existing)
            self.assertEqual(audit["status"], "blocked")
            self.assertIn("budget", audit["reason"])


if __name__ == "__main__":
    unittest.main()
