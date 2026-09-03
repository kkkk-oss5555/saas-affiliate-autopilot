import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pipeline import affiliate_url, build_png, decision, select_topic


class PipelineTests(unittest.TestCase):
    def test_affiliate_url_removes_www_and_tracks(self):
        url = affiliate_url("https://www.systeme.io/", "sa123", "pin-1")
        self.assertEqual(url, "https://systeme.io/?sa=sa123&tk=pin-1")

    def test_topic_selection_is_deterministic(self):
        topics = [{"topic_id": "a", "intent": "5", "evergreen": "5", "saturation": "3"}, {"topic_id": "b", "intent": "1", "evergreen": "1", "saturation": "5"}]
        self.assertEqual(select_topic(topics, date(2026, 9, 3))["topic_id"], "a")

    def test_30_day_stop(self):
        status, _ = decision(30, {"impressions": 500, "outbound_clicks": 25, "signups": 0, "sales": 0, "ctr": .05})
        self.assertEqual(status, "NO-GO")

    def test_png_generation(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "pin.png"
            build_png(path)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
