import tempfile
import unittest
from pathlib import Path

from src.evaluators.job_evaluator import build_job_payload
from src.reporting.prompt_export import batch_jobs_for_prompts, export_evaluation_prompts


class PromptExportTests(unittest.TestCase):
    def test_build_job_payload_trims_boilerplate_from_description(self):
        job = {
            "job_id": "job-1",
            "company": "Acme",
            "title": "Platform Architect",
            "location": "Remote, United States",
            "description_text": (
                "About the role\n"
                "Lead architecture decisions across platform systems.\n\n"
                "Responsibilities\n"
                "Drive integration strategy and IAM alignment.\n\n"
                "Equal Opportunity Employer\n"
                "All qualified applicants will receive consideration for employment.\n"
            ),
        }

        payload = build_job_payload(job)

        self.assertIn("description_excerpt", payload)
        self.assertIn("Lead architecture decisions", payload["description_excerpt"])
        self.assertNotIn("Equal Opportunity Employer", payload["description_excerpt"])

    def test_batch_jobs_for_prompts_honors_batch_size(self):
        jobs = [
            {"job_id": f"job-{index}", "company": "Acme", "title": f"Role {index}"}
            for index in range(1, 8)
        ]

        batches = batch_jobs_for_prompts(jobs, max_jobs_per_batch=3, max_chars_per_batch=100000)

        self.assertEqual([len(batch) for batch in batches], [3, 3, 1])

    def test_export_evaluation_prompts_writes_index_and_batch_files(self):
        jobs = [
            {
                "job_id": f"job-{index}",
                "company": "Acme",
                "title": f"Role {index}",
                "location": "Remote, United States",
                "detail_status": "maybe",
                "detail_reasons": "Role fit is ambiguous",
            }
            for index in range(1, 6)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_dir = Path(tmpdir) / "evaluation_prompts"
            index_file = Path(tmpdir) / "evaluation_prompts.md"

            written_files = export_evaluation_prompts(
                jobs,
                prompt_dir=str(prompt_dir),
                index_filename=str(index_file),
                max_jobs_per_batch=2,
                max_chars_per_batch=100000,
            )

            self.assertEqual(len(written_files), 3)
            self.assertTrue((prompt_dir / "batch_001.md").exists())
            self.assertTrue((prompt_dir / "batch_002.md").exists())
            self.assertTrue((prompt_dir / "batch_003.md").exists())

            index_text = index_file.read_text(encoding="utf-8")
            batch_text = (prompt_dir / "batch_001.md").read_text(encoding="utf-8")

            self.assertIn("batch_001.md", index_text)
            self.assertIn("return only a json array", batch_text.lower())
            self.assertIn("job_id: job-1", batch_text)


if __name__ == "__main__":
    unittest.main()
