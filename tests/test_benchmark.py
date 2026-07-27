import unittest

from evaluation.benchmark import MIN_TOP1, evaluate
from evaluation.generate import generate_cases


class TestBenchmark(unittest.TestCase):
    def test_corpus_has_labelled_and_noise_cases(self):
        cases = generate_cases()
        self.assertTrue(any(c.ground_truth for c in cases))
        self.assertTrue(any(c.ground_truth is None for c in cases))

    def test_ranking_meets_quality_bar(self):
        metrics = evaluate()
        self.assertGreaterEqual(
            metrics.top1, MIN_TOP1,
            f"Top-1 accuracy {metrics.top1:.0%} regressed below {MIN_TOP1:.0%}",
        )
        self.assertGreaterEqual(metrics.top3, metrics.top1)

    def test_no_false_positives_on_noise(self):
        metrics = evaluate()
        self.assertEqual(metrics.false_positives, 0)


if __name__ == "__main__":
    unittest.main()
