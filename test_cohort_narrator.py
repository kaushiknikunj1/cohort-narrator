"""Run: python test_cohort_narrator.py   (unittest only, no API key needed)"""
import os
import unittest

import numpy as np

os.environ["LLM_PROVIDER"] = "none"
import cohort_narrator as cn  # noqa: E402
import llm  # noqa: E402

TRI, RES, FINDINGS, AGG = cn.analyse()


class TriangleTests(unittest.TestCase):
    def test_triangle_shape_and_censoring(self):
        self.assertEqual(TRI.shape, (15, cn.MAX_AGE + 1))
        self.assertTrue((TRI[0] == 100).all(), "everyone is active in the signup month")
        self.assertTrue(np.isnan(TRI.loc["2026-09", 2]), "ages past the cutoff month are unobserved")
        self.assertFalse(np.isnan(TRI.loc["2025-07", 12]))
        observed = TRI.notna().sum(axis=1).tolist()
        self.assertEqual(observed, sorted(observed, reverse=True), "newer cohorts have fewer observed ages")
        self.assertEqual(observed[-1], 2, "the newest cohort has months 0 and 1 only")

    def test_finds_the_three_injected_stories(self):
        by_type = {f["type"]: f for f in FINDINGS}
        self.assertEqual(sorted(by_type), ["diagonal", "row", "vertical"])
        self.assertEqual(by_type["row"]["cohort"], cn.PAID_COHORT)
        self.assertLess(by_type["row"]["gap_pp"], -8)
        self.assertEqual(by_type["vertical"]["from_cohort"], cn.PRODUCT_CHANGE)
        self.assertGreater(by_type["vertical"]["gap_pp"], 5)
        self.assertEqual(by_type["diagonal"]["calendar_month"], cn.OUTAGE_MONTH)
        self.assertLess(by_type["diagonal"]["mean_gap_pp"], -3)
        self.assertEqual(len(FINDINGS), 3, "no false positives on the clean cells")

    def test_blended_curve_hides_the_improvement(self):
        m3 = AGG["month_3"]
        self.assertGreater(m3["mix_gap_pp"], 2, "equal-weighted sits above size-weighted at month 3")
        self.assertLess(abs(m3["blended_pct"] - m3["baseline_pct"]), 1.5, "the blended headline looks flat")
        self.assertGreater(m3["post_change_mean_pct"] - m3["baseline_pct"], 5, "recent cohorts are better")
        self.assertGreater(m3["bad_row_weight_pct"], m3["post_change_weight_pct"])

    def test_projection_for_latest_cohorts(self):
        proj = AGG["projection"]["latest_cohorts"]
        self.assertEqual(len(proj), 5)
        for p in proj:
            self.assertGreater(p["projected_month_12_pct"], AGG["projection"]["baseline_month_12_pct"])
            self.assertLess(p["projected_month_12_pct"], 40)


class AlgorithmTests(unittest.TestCase):
    def test_changepoint_on_hand_example(self):
        x = np.array([0.0, 0.1, -0.1, 0.0, 5.0, 5.1, 4.9, 5.0])
        k, shift = cn.changepoint(x)
        self.assertEqual(k, 4)
        self.assertAlmostEqual(shift, 5.0, places=6)

    def test_fit_curve_recovers_power_law(self):
        ages = np.arange(1, 13, dtype=float)
        c, b, k = cn.fit_curve(ages, 20 + 30 * ages ** -0.75)
        self.assertAlmostEqual(c, 20, delta=0.3)
        self.assertAlmostEqual(k, 0.75, delta=0.02)
        self.assertAlmostEqual(b, 30, delta=0.5)


class NarrativeTests(unittest.TestCase):
    def test_templates_render_without_a_key(self):
        for ev in FINDINGS:
            text, src = cn.narrate(ev, cn.SYSTEM_FINDING, cn.template_finding)
            self.assertEqual(src, "template (no API key)")
            self.assertEqual(len(text.split("\n")), 2)
            self.assertEqual(llm.unpinned(text, ev), set(), "template only uses evidence numbers")
        summary, src = cn.narrate(AGG, cn.SYSTEM_SUMMARY, cn.template_summary)
        self.assertEqual(src, "template (no API key)")
        self.assertIn("Blended month-3 retention", summary)

    def test_unpinned_catches_an_invented_number(self):
        ev = next(f for f in FINDINGS if f["type"] == "row")
        clean = cn.template_finding(ev)
        self.assertEqual(llm.unpinned(clean, ev), set())
        self.assertEqual(llm.unpinned(clean.replace(f"{ev['observed_pct']}%", "19.9%"), ev), {"19.9"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
