import csv
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from autopilot import apply_decisions, evaluate_performance, run, select_candidate
from pipeline import read_csv
from publish_pinterest import main as publish_main


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "config").mkdir()
        (self.root / "data").mkdir()
        (self.root / "generated").mkdir()
        for item in ["config/settings.json", "data/offers.csv", "data/topics_en.csv", "data/performance.csv"]:
            shutil.copy(REPO / item, self.root / item)

    def test_dry_run_does_not_change_state_or_files(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        summary = run(self.root, date(2026, 9, 24), dry_run=True)
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before, after)
        self.assertEqual(summary["quality_result"], "PASS")
        self.assertEqual(summary["pins_created"], 3)

    def test_cycle_creates_tracked_queue_and_moves_to_next_topic(self):
        first = run(self.root, date(2026, 9, 24))
        rows = read_csv(self.root / "generated/autopilot_queue.csv")
        self.assertEqual(len(rows), 3)
        self.assertTrue((self.root / first["generated_article"]).exists())
        self.assertEqual({r["topic_id"] for r in rows}, {first["selected_topic"]})
        self.assertEqual(len({r["pin_id"] for r in rows}), 3)
        self.assertEqual(len({r["title"] for r in rows}), 3)
        self.assertEqual(len({r["image_url"] for r in rows}), 3)
        for row in rows:
            self.assertIn("utm_source=pinterest", row["destination_url"])
            self.assertIn("utm_content=" + row["pin_id"], row["destination_url"])
            self.assertEqual(row["status"], "WAITING_FOR_STANDARD")
            self.assertTrue((self.root / f"generated/images/{row['pin_id']}.png").exists())
        second = run(self.root, date(2026, 10, 1))
        self.assertNotEqual(first["selected_topic"], second["selected_topic"])
        self.assertEqual(len(read_csv(self.root / "generated/autopilot_queue.csv")), 6)

    def test_selection_skips_same_keyword_and_paused(self):
        topics = [{"topic_id": "one", "keyword": "Email setup", "intent": "5", "evergreen": "5", "saturation": "1"}, {"topic_id": "two", "keyword": "email SETUP!", "intent": "4", "evergreen": "5", "saturation": "1"}, {"topic_id": "three", "keyword": "Other topic", "intent": "3", "evergreen": "5", "saturation": "1"}]
        state = {"processed": {"one": {"keyword": "Email setup"}}, "paused": [], "expansion_candidates": []}
        self.assertEqual(select_candidate(topics, state)["topic_id"], "three")

    def test_performance_uses_real_topic_data_and_windows(self):
        created = date(2026, 9, 1)
        self.assertEqual(evaluate_performance([], "a", created, date(2026, 10, 1))["decision"], "INSUFFICIENT_DATA")
        strong = [{"date": "2026-09-08", "topic_id": "a", "impressions": "200", "outbound_clicks": "10", "signups": "0", "sales": "0"}]
        self.assertEqual(evaluate_performance(strong, "a", created, date(2026, 9, 8))["decision"], "EXPAND")
        weak = [{"date": "2026-09-15", "topic_id": "a", "impressions": "400", "outbound_clicks": "0", "signups": "0", "sales": "0"}]
        self.assertEqual(evaluate_performance(weak, "a", created, date(2026, 9, 15))["decision"], "PAUSE")
        self.assertEqual(evaluate_performance(strong, "b", created, date(2026, 9, 8))["decision"], "INSUFFICIENT_DATA")

    def test_expand_adds_once_and_pause_removes_child(self):
        state = {"processed": {"a": {"created_at": "2026-09-01", "keyword": "email setup", "pain": "it is slow", "offer_id": "systeme_io"}}, "paused": [], "expansion_candidates": []}
        strong = [{"date": "2026-09-08", "topic_id": "a", "impressions": "200", "outbound_clicks": "10"}]
        apply_decisions(state, strong, date(2026, 9, 8))
        apply_decisions(state, strong, date(2026, 9, 8))
        self.assertEqual(len(state["expansion_candidates"]), 1)
        weak = [{"date": "2026-09-15", "topic_id": "a", "impressions": "400", "outbound_clicks": "0"}]
        apply_decisions(state, weak, date(2026, 9, 15))
        self.assertEqual(state["paused"], ["a"])
        self.assertEqual(state["expansion_candidates"], [])

    def test_publisher_is_off_without_explicit_standard_configuration(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(publish_main())


if __name__ == "__main__":
    unittest.main()
