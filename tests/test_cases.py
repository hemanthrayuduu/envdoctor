import unittest

from envdoctor.diff import diff_fingerprints
from envdoctor.rank import rank_causes
from evaluation.benchmark import evaluate
from evaluation.cases_loader import load_real_world_cases


class TestRealWorldCases(unittest.TestCase):
    def setUp(self):
        self.cases = load_real_world_cases()

    def test_corpus_is_non_empty(self):
        self.assertGreaterEqual(len(self.cases), 5)

    def test_every_case_has_a_detectable_difference(self):
        for case in self.cases:
            diffs = diff_fingerprints(case.working, case.failing)
            self.assertTrue(diffs, f"{case.name}: no difference detected")

    def test_ground_truth_is_top_ranked(self):
        # Every curated case's true cause should rank #1.
        for case in self.cases:
            diffs = diff_fingerprints(case.working, case.failing)
            causes = rank_causes(diffs, traceback_text=case.traceback)
            self.assertTrue(causes, f"{case.name}: engine found no cause")
            top = (causes[0].difference.category, causes[0].difference.key)
            self.assertEqual(
                top, case.ground_truth,
                f"{case.name}: expected {case.ground_truth} at #1, got {top}",
            )

    def test_benchmark_metrics_on_real_corpus(self):
        metrics = evaluate(self.cases)
        self.assertEqual(metrics.top1, 1.0)
        self.assertEqual(metrics.false_positives, 0)


if __name__ == "__main__":
    unittest.main()
