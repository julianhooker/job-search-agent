import unittest

from src.reporting.evaluation_queue import build_evaluation_queue, is_manual_evaluation_candidate, summarize_queue


class EvaluationQueueTests(unittest.TestCase):
    def test_manual_evaluation_candidates_only_include_keep_maybe_and_legacy_review(self):
        self.assertTrue(is_manual_evaluation_candidate({"detail_status": "keep"}))
        self.assertTrue(is_manual_evaluation_candidate({"detail_status": "maybe"}))
        self.assertTrue(is_manual_evaluation_candidate({"detail_status": "review"}))
        self.assertFalse(is_manual_evaluation_candidate({"detail_status": "reject"}))
        self.assertFalse(is_manual_evaluation_candidate({"prefilter_status": "reject"}))

    def test_queue_preserves_auto_rejects_without_marking_them_ready_for_evaluation(self):
        candidate_jobs = [
            {
                "job_id": "job-keep",
                "title": "Platform Architect",
                "company": "Acme",
                "detail_status": "keep",
            },
            {
                "job_id": "job-maybe",
                "title": "Security Engineer",
                "company": "Acme",
                "detail_status": "maybe",
            },
        ]
        skipped_jobs = [
            {
                "job_id": "job-prefilter-reject",
                "title": "Sales Executive",
                "company": "Acme",
                "prefilter_status": "reject",
            },
            {
                "job_id": "job-detail-reject",
                "title": "Implementation Manager",
                "company": "Acme",
                "detail_status": "reject",
            },
        ]
        eval_results = [{"job_id": "job-maybe"}]
        merged_results = [{"job_id": "job-keep"}]

        queue_items = build_evaluation_queue(
            candidate_jobs=candidate_jobs,
            skipped_jobs=skipped_jobs,
            eval_results=eval_results,
            merged_results=merged_results,
        )

        by_id = {item["job_id"]: item for item in queue_items}
        self.assertEqual(by_id["job-keep"]["status"], "merged")
        self.assertEqual(by_id["job-maybe"]["status"], "evaluated")
        self.assertEqual(by_id["job-prefilter-reject"]["status"], "skipped")
        self.assertEqual(by_id["job-detail-reject"]["status"], "skipped")
        self.assertFalse(by_id["job-prefilter-reject"]["ready_for_evaluation"])
        self.assertFalse(by_id["job-detail-reject"]["ready_for_evaluation"])

        counts = summarize_queue(queue_items)
        self.assertEqual(counts["pending"], 0)
        self.assertEqual(counts["evaluated"], 1)
        self.assertEqual(counts["merged"], 1)
        self.assertEqual(counts["skipped"], 2)


if __name__ == "__main__":
    unittest.main()
