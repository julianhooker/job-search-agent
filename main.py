from src.collectors.greenhouse import collect_greenhouse_jobs
from src.utils.config_loader import load_companies
from src.reporting.csv_export import export_jobs_csv
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

    kept_jobs, rejected_jobs = prefilter_jobs(all_jobs)

    print(f"Collected {len(all_jobs)} total jobs")
    print(f"Kept {len(kept_jobs)} jobs after prefilter")
    print(f"Rejected {len(rejected_jobs)} jobs after prefilter")

    export_jobs_csv(kept_jobs, "reports/jobs.csv")
    export_jobs_csv(rejected_jobs, "reports/rejected_jobs.csv")


if __name__ == "__main__":
    main()