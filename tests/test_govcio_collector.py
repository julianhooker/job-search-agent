import json
import unittest
from pathlib import Path

from src.collectors.govcio import (
    _clean_description_text,
    _extract_salary_fields,
    _matches_preferences,
    _normalize_job_record,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class GovCIOCollectorTests(unittest.TestCase):
    def load_fixture(self, name):
        return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))

    def test_normalize_job_record_builds_expected_identity_and_fields(self):
        detail = self.load_fixture("govcio_job_detail.json")

        job = _normalize_job_record("govcio", detail, "GovCIO")

        self.assertEqual(job["job_id"], "govcio:govcio:7993")
        self.assertEqual(job["source"], "govcio")
        self.assertEqual(job["company"], "GovCIO")
        self.assertEqual(job["url"], "https://careers.govcio.com/careers-home/jobs/7993?lang=en-us")
        self.assertEqual(job["application_url"], "https://careers-govcio.icims.com/jobs/7993/login")
        self.assertEqual(job["clearance"], "Secret")
        self.assertEqual(job["employment_type"], "Full-time")
        self.assertEqual(job["workplace_type"], "onsite")
        self.assertEqual(job["salary_text"], "USD $28.84 - USD $33.65 /Hr")
        self.assertIsNone(job["salary_min"])
        self.assertIsNone(job["salary_max"])
        self.assertIn("Responsibilities", job["description_text"])
        self.assertIn("Qualifications", job["description_text"])

    def test_extract_salary_fields_keeps_hourly_human_readable_without_numeric_range(self):
        salary_text, salary_min, salary_max = _extract_salary_fields(
            "Posted Salary Range\nUSD $28.84 - USD $33.65 /Hr."
        )

        self.assertEqual(salary_text, "USD $28.84 - USD $33.65 /Hr")
        self.assertIsNone(salary_min)
        self.assertIsNone(salary_max)

    def test_extract_salary_fields_parses_annual_ranges_for_filtering(self):
        salary_text, salary_min, salary_max = _extract_salary_fields(
            "Posted Salary Range\nUSD $120,000.00 - USD $125,000.00 /Yr."
        )

        self.assertEqual(salary_text, "USD $120,000.00 - USD $125,000.00 /Yr")
        self.assertEqual(salary_min, 120000)
        self.assertEqual(salary_max, 125000)

    def test_clean_description_text_stops_before_generic_company_boilerplate(self):
        cleaned = _clean_description_text(
            "<p>Overview</p><p>Relevant role content.</p><p><strong>Company Overview</strong></p><p>Generic company text.</p>"
        )

        self.assertIn("Overview", cleaned)
        self.assertIn("Relevant role content.", cleaned)
        self.assertIn("Company Overview", cleaned)
        self.assertNotIn("Generic company text.", cleaned)

    def test_matches_preferences_accepts_fully_remote_preferred_categories(self):
        self.assertTrue(
            _matches_preferences(
                {
                    "categories": [{"name": "Information Technology"}],
                    "tags2": ["Fully remote"],
                }
            )
        )

    def test_matches_preferences_rejects_nonpreferred_categories_or_nonremote_jobs(self):
        self.assertFalse(
            _matches_preferences(
                {
                    "categories": [{"name": "Marketing/Communications/Media & Research"}],
                    "tags2": ["Fully remote"],
                }
            )
        )
        self.assertFalse(
            _matches_preferences(
                {
                    "categories": [{"name": "Information Technology"}],
                    "tags2": ["Hybrid schedule"],
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
