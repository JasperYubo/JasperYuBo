from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_profile_stats.py"
SPEC = importlib.util.spec_from_file_location("render_profile_stats", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RenderProfileStatsTests(unittest.TestCase):
    def test_stats_svg_is_valid_and_escapes_username(self) -> None:
        result = MODULE.render_stats(
            {
                "username": "Yu<Bo>",
                "repositories": 6,
                "stars": 12,
                "forks": 3,
                "followers": 9,
            }
        )
        ET.fromstring(result)
        self.assertIn("Yu&lt;Bo&gt;", result)
        self.assertNotIn("github-readme-stats.vercel.app", result)

    def test_language_rows_are_deterministic_percentages(self) -> None:
        rows = MODULE.language_rows(Counter({"HTML": 75, "JavaScript": 25}))
        self.assertEqual(rows[0], ("HTML", 75, 75.0))
        self.assertEqual(rows[1], ("JavaScript", 25, 25.0))
        result = MODULE.render_languages(Counter({"HTML": 75, "JavaScript": 25}))
        ET.fromstring(result)
        self.assertIn("75.0%", result)
        self.assertIn("25.0%", result)

    def test_empty_language_card_is_valid(self) -> None:
        result = MODULE.render_languages(Counter())
        ET.fromstring(result)
        self.assertIn("暂无可统计", result)


if __name__ == "__main__":
    unittest.main()
