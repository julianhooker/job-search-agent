import unittest

from src.filters.detail_filter import classify_role_fit
from src.filters.prefilter import classify_location, prefilter_job


class FilterTests(unittest.TestCase):
    def test_prefilter_rejects_actuarial_titles(self):
        result = prefilter_job(
            {
                "title": "Senior Actuarial Analyst",
                "location": "Remote, Washington DC",
                "workplace_type": "remote",
                "employment_type": "Full-time",
            }
        )

        self.assertEqual(result["status"], "reject")
        self.assertTrue(any("outside target role family" in reason.lower() for reason in result["reasons"]))

    def test_detail_filter_rejects_actuarial_role_context(self):
        status, reasons = classify_role_fit(
            {
                "title": "Senior Actuarial Analyst",
                "metadata": "Analytics - Actuarial Team",
                "description_text": "Build actuarial models and pricing analyses.",
            }
        )

        self.assertEqual(status, "reject")
        self.assertTrue(any("outside target area" in reason.lower() for reason in reasons))

    def test_prefilter_rejects_performance_excellence_titles(self):
        result = prefilter_job(
            {
                "title": "Senior Director of Performance Excellence",
                "location": "Remote, Arlington, VA",
                "workplace_type": "remote",
                "employment_type": "Full-time",
            }
        )

        self.assertEqual(result["status"], "reject")
        self.assertTrue(any("outside target role family" in reason.lower() for reason in result["reasons"]))

    def test_detail_filter_rejects_performance_excellence_role_context(self):
        status, reasons = classify_role_fit(
            {
                "title": "Senior Director of Performance Excellence",
                "metadata": "Operational owner for performance excellence",
                "description_text": "Drive performance excellence across business units and steering committees.",
            }
        )

        self.assertEqual(status, "reject")
        self.assertTrue(any("outside target area" in reason.lower() for reason in reasons))

    def test_prefilter_rejects_business_ops_titles(self):
        for title in (
            "Director of Business Performance",
            "Field CTO, Public Sector",
            "Medical Records Retrieval Associate",
            "Principal Cybersecurity Incident Manager (USA)",
            "Pyramid Analytics Architect",
            "Senior Manager, Performance Data Operations",
            "Service Desk Manager",
            "Senior Manager, Operational Excellence",
            "Steering Committee Program Lead",
        ):
            result = prefilter_job(
                {
                    "title": title,
                    "location": "Remote, United States",
                    "workplace_type": "remote",
                    "employment_type": "Full-time",
                }
            )

            self.assertEqual(result["status"], "reject", msg=title)
            self.assertTrue(
                any("outside target role family" in reason.lower() for reason in result["reasons"]),
                msg=title,
            )

    def test_prefilter_does_not_reject_plain_technical_operations_title(self):
        result = prefilter_job(
            {
                "title": "Senior IT Operations Engineer II",
                "location": "Remote, United States",
                "workplace_type": "remote",
                "employment_type": "Full-time",
            }
        )

        self.assertNotEqual(result["status"], "reject")

    def test_location_rejects_remote_bangalore_as_non_us(self):
        status, reasons = classify_location("Remote, Bangalore", "remote")

        self.assertEqual(status, "reject")
        self.assertTrue(any("non-us" in reason.lower() for reason in reasons))


if __name__ == "__main__":
    unittest.main()
