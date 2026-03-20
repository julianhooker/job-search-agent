import argparse
import json

from src.collectors.registry import get_collector
from src.utils.config_loader import load_companies
from src.utils.id_helpers import require_job_ids


EXPECTED_BASE_FIELDS = (
    "title",
    "location",
    "url",
    "external_job_id",
    "internal_job_id",
    "company_slug",
    "company",
    "source",
    "job_id",
)


def _sample_record(job):
    keys = [
        "job_id",
        "title",
        "company",
        "source",
        "location",
        "url",
        "employment_type",
        "travel_text",
        "salary_text",
        "salary_min",
        "salary_max",
        "metadata",
    ]
    return {key: job.get(key) for key in keys}


def run_collector_smoke_test(company_name):
    companies = load_companies(company_names=[company_name])
    if not companies:
        raise ValueError(f"No company named {company_name!r} found in config/companies.yaml")

    company = companies[0]
    collector = get_collector(company["platform"])
    if not collector:
        raise ValueError(f"Unsupported collector platform: {company['platform']}")

    print(f"Smoke testing collector for {company['name']} ({company['platform']})")
    print(f"Configured URL: {company['url']}")

    jobs = collector(company["url"], company_name=company.get("name"))
    fetched_count = len(jobs)
    print(f"Jobs fetched: {fetched_count}")

    require_job_ids(jobs, stage_name="collector_smoke_test")

    normalized_count = 0
    missing_field_counts = {field: 0 for field in EXPECTED_BASE_FIELDS}
    unique_job_ids = set()

    for job in jobs:
        normalized_count += 1
        unique_job_ids.add(job["job_id"])
        for field in EXPECTED_BASE_FIELDS:
            if not job.get(field):
                missing_field_counts[field] += 1

    print(f"Jobs normalized successfully: {normalized_count}")
    print(f"Unique job_ids: {len(unique_job_ids)}")
    print("Missing expected field counts:")
    for field in EXPECTED_BASE_FIELDS:
        print(f"- {field}: {missing_field_counts[field]}")

    sample_jobs = jobs[:2]
    if sample_jobs:
        print("Sample normalized records:")
        for job in sample_jobs:
            print(json.dumps(_sample_record(job), indent=2, ensure_ascii=False))
    else:
        print("Sample normalized records: none")


def main():
    parser = argparse.ArgumentParser(description="Smoke test one configured ATS company collector.")
    parser.add_argument("--company", required=True, help="Configured company name from config/companies.yaml")
    args = parser.parse_args()
    run_collector_smoke_test(args.company)


if __name__ == "__main__":
    main()
