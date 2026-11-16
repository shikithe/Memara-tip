import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone
from nba_clear_before_collect import clear,ACTIVE_SNAPSHOTS

class NbaPrecollectionResetTests(unittest.TestCase):
    def test_clear_only_nba_active_offers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/"collector-output"
            folder.mkdir()
            for name in ACTIVE_SNAPSHOTS:
                (folder/name).write_text('{"offers":[{"stale":true}],"games":[1],"players":[1]}')
            (root/"data.json").write_text('{"tickets":[{"id":"C"}]}')
            (root/"archive.json").write_text('[{"date":"2026-11-15"}]')
            (root/"collector-feed.json").write_text('{"football_candidates":[1]}')
            changed=clear(root,datetime(2026,11,16,11,0,tzinfo=timezone.utc))
            self.assertEqual(len(changed),len(ACTIVE_SNAPSHOTS))
            for name in ACTIVE_SNAPSHOTS:
                state=json.loads((folder/name).read_text())
                self.assertEqual(state.get("games",[]),[])
                self.assertEqual(state.get("players",[]),[])
                self.assertEqual(state.get("offers",[]),[])
                self.assertFalse(state["publication_allowed"])
                self.assertEqual(state["cleared_at_utc"],"2026-11-16T11:00:00+00:00")
            self.assertEqual((root/"data.json").read_text(),'{"tickets":[{"id":"C"}]}')
            self.assertEqual((root/"archive.json").read_text(),'[{"date":"2026-11-15"}]')
            self.assertEqual((root/"collector-feed.json").read_text(),'{"football_candidates":[1]}')
if __name__=="__main__":unittest.main()
