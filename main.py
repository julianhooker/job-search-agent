from src.collectors.greenhouse import collect_greenhouse_jobs
from src.collectors.job_details import enrich_jobs_with_details
from src.utils.config_loader import load_companies
from src.reporting.csv_export import export_jobs_csv
from src.reporting.json_export import export_jobs_json
from src.filters.prefilter import prefilter_jobs


def main():
    companies = load_companies()
    all_jobs = []

    for company in companies:
        if company["platform"] == "greenhouse":
            print(f"Collecting jobs from {company['name']}")
            jobs = collect_greenhouse_jobs(company["url"])

            for job in jobs:
                job["company"] = company["name"]

            all_jobs.extend(jobs)

    kept_jobs, maybe_jobs, rejected_jobs = prefilter_jobs(all_jobs)

    print(f"Collected {len(all_jobs)} total jobs")
    print(f"Kept {len(kept_jobs)} jobs after prefilter")
    print(f"Maybe {len(maybe_jobs)} jobs after prefilter")
    print(f"Rejected {len(rejected_jobs)} jobs after prefilter")

    review_jobs = kept_jobs + maybe_jobs
    enriched_review_jobs = enrich_jobs_with_details(review_jobs)

    export_jobs_csv(kept_jobs, "reports/jobs_keep.csv")
    export_jobs_csv(maybe_jobs, "reports/jobs_maybe.csv")
    export_jobs_csv(rejected_jobs, "reports/jobs_rejected.csv")

    export_jobs_json(enriched_review_jobs, "reports/jobs_review.json")


if __name__ == "__main__":
    main()