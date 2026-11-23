"""Protect score/minute tracking after ticket publication (no network)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT/path).read_text(encoding="utf-8")


class LiveMonitoringContract(unittest.TestCase):
    def test_football_browser_fallback_uses_published_fixture_ids(self):
        ui=read("index.html")
        self.assertIn("async function checkEspnDirectly()",ui)
        self.assertIn("currentData.tickets",ui)
        self.assertIn("leg.fixture_id",ui)
        self.assertIn("event_id:job.eventId",ui)
        self.assertIn("scoreDate(leg.start_sarajevo",ui)
        self.assertIn("espn-browser-direct",ui)
        self.assertIn("minute:final?null",ui)

    def test_clocks_are_visible_and_stale_is_explicit(self):
        ui=read("index.html")
        self.assertIn("live.match_phase==='half_time'",ui)
        self.assertIn("live.game_clock",ui)
        self.assertIn("preostalo",ui)
        self.assertIn("state:'stale'",ui)
        self.assertIn("Posljednji zabilježeni rezultat",ui)

    def test_main_ticket_publication_starts_score_checks(self):
        ab=read(".github/workflows/memarasix-espn-ab-publish.yml")
        c=read(".github/workflows/memarasix-scheduled-publication.yml")
        live=read(".github/workflows/memarasix-live-scores.yml")
        for publisher in (ab,c):
            self.assertIn("gh workflow run memarasix-live-scores.yml",publisher)
            self.assertIn("actions: write",publisher)
        self.assertIn("'data.json'",live)
        self.assertIn("cron: '*/5 * * * *'",live)

    def test_nba_system_has_independent_refresh(self):
        nba=read(".github/workflows/nba-system-live.yml")
        publisher=read(".github/workflows/nba-system-scout-publish.yml")
        self.assertIn("cron: '*/5 * * * *'",nba)
        self.assertIn("gh workflow run nba-system-live.yml",publisher)
        self.assertIn("nba_system_live.py",nba)

    def test_bank_is_not_modified_from_browser(self):
        ui=read("index.html")
        self.assertIn("banku potvrđuje GitHub",ui)
        self.assertIn("data.json?v=",ui)
        self.assertIn("live-scores.json?v=",ui)


if __name__=="__main__":
    unittest.main()
