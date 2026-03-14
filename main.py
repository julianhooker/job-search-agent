from src.collectors.greenhouse import collect_greenhouse_jobs
from src.collectors.job_details import enrich_jobs_with_details
from src.utils.config_loader import load_companies
from src.reporting.csv_export import export_jobs_csv
from src.reporting.json_export import export_jobs_json
from src.reporting.prompt_export import export_evaluation_prompts
from src.filters.prefilter import prefilter_jobs
from src.filters.detail_filter import detail_filter_jobs
from src.evaluators.job_evaluator import build_evaluation_prompt
from src.reporting.daily_report import build_daily_report


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

    detail_keep, detail_maybe, detail_reject = detail_filter_jobs(enriched_review_jobs)

    print(f"Kept {len(detail_keep)} jobs after detail filter")
    print(f"Maybe {len(detail_maybe)} jobs after detail filter")
    print(f"Rejected {len(detail_reject)} jobs after detail filter")

    export_jobs_csv(kept_jobs, "reports/jobs_keep.csv")
    export_jobs_csv(maybe_jobs, "reports/jobs_maybe.csv")
    export_jobs_csv(rejected_jobs, "reports/jobs_rejected.csv")

    export_jobs_json(enriched_review_jobs, "reports/jobs_review.json")

    export_jobs_csv(detail_keep, "reports/jobs_detail_keep.csv")
    export_jobs_csv(detail_maybe, "reports/jobs_detail_maybe.csv")
    export_jobs_csv(detail_reject, "reports/jobs_detail_reject.csv")
    export_jobs_json(detail_keep + detail_maybe + detail_reject, "reports/jobs_detail_review.json")

    evaluator_jobs = detail_keep + detail_maybe
    export_evaluation_prompts(
        evaluator_jobs,
        build_evaluation_prompt,
        "reports/evaluation_prompts.md",
    )

    daily_candidates = detail_keep + detail_maybe

    build_daily_report(daily_candidates)

if __name__ == "__main__":
    main()