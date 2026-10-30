import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from memarasix_publication_gate import assess

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("Europe/Sarajevo"))

class GateTests(unittest.TestCase):
    def test_stale_feed_blocks_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = '{"date":"2026-10-30","bank_after":164.33,"tickets":[]}'
            (root / "data.json").write_text(original)
            (root / "collector-feed.json").write_text('{"date":"2026-10-30"}')
            self.assertIn("stale", assess(root, NOW))
            self.assertEqual((root / "data.json").read_text(), original)

    def test_fresh_feed_without_odds_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data.json").write_text('{"date":"2026-10-30","tickets":[]}')
            (root / "collector-feed.json").write_text('{"date":"2026-10-31"}')
            self.assertIn("no verified", assess(root, NOW))

    def test_published_tickets_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = '{"date":"2026-10-31","tickets":[{"status":"objavljen"}]}'
            (root / "data.json").write_text(original)
            self.assertIn("immutable", assess(root, NOW))
            self.assertEqual((root / "data.json").read_text(), original)

if __name__ == "__main__":
    unittest.main()
