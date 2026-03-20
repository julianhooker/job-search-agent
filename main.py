import os

from src.collectors.registry import get_collector
from src.collectors.job_details import enrich_jobs_with_details
from src.utils.config_loader import load_companies
from src.reporting.csv_export import export_jobs_csv
from src.reporting.json_export import export_jobs_json
from src.reporting.prompt_export import export_evaluation_prompts
from src.reporting.evaluation_queue import (
    build_evaluation_queue,
    load_json_file as load_queue_input_json,
    pending_jobs_from_queue,
    print_queue_summary,
    write_evaluation_queue,
)
from src.reporting.final_report import run_final_report
from src.filters.prefilter import prefilter_jobs
from src.filters.detail_filter import detail_filter_jobs
from src.evaluators.job_evaluator import build_evaluation_prompt, build_evaluation_prompt_preamble
from src.reporting.daily_report import build_daily_report
from src.utils.id_helpers import require_job_ids


def main():
    company_filter_env = os.getenv("COMPANY_FILTER", "").strip()
    company_filter = [name.strip() for name in company_filter_env.split(",") if name.strip()] if company_filter_env else None
    companies = load_companies(company_names=company_filter)
    all_jobs = []

    if company_filter and not companies:
        raise ValueError(f"No companies matched COMPANY_FILTER={company_filter_env!r}")

    for company in companies:
        platform = company["platform"]
        collector = get_collector(platform)
        if collector:
            print(f"Collecting jobs from {company['name']}")
            jobs = collector(company["url"], company_name=company.get("name"))

            # ensure identity fields are present for all collected jobs
            require_job_ids(jobs, stage_name="collection")

            # company name is provided by collector but ensure consistency
            for job in jobs:
                if not job.get("company"):
                    job["company"] = company["name"]

            all_jobs.extend(jobs)
        else:
            raise ValueError(f"Unsupported collector platform: {platform}")

    kept_jobs, maybe_jobs, rejected_jobs = prefilter_jobs(all_jobs)

    # Validate identity fields after prefiltering (on the source list)
    require_job_ids(all_jobs, stage_name="after_prefilter")

    print(f"Collected {len(all_jobs)} total jobs")
    print(f"Kept {len(kept_jobs)} jobs after prefilter")
    print(f"Maybe {len(maybe_jobs)} jobs after prefilter")
    print(f"Rejected {len(rejected_jobs)} jobs after prefilter")

    review_jobs = kept_jobs + maybe_jobs
    enriched_review_jobs = enrich_jobs_with_details(review_jobs)

    # Validate identity fields after enrichment
    require_job_ids(enriched_review_jobs, stage_name="after_enrichment")

    detail_keep, detail_maybe, detail_reject = detail_filter_jobs(enriched_review_jobs)

    # Validate identity fields after detail filtering
    require_job_ids(detail_keep + detail_maybe + detail_reject, stage_name="after_detail_filter")

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
    evaluator_jobs_by_id = {job["job_id"]: job for job in evaluator_jobs}

    # Final check before generating evaluation prompts
    require_job_ids(evaluator_jobs, stage_name="before_prompt_export")

    existing_eval_results = load_queue_input_json("reports/evaluator_results.json")
    existing_merged_results = load_queue_input_json("reports/evaluator_results_merged.json")
    evaluation_queue = build_evaluation_queue(
        candidate_jobs=evaluator_jobs,
        skipped_jobs=detail_reject,
        eval_results=existing_eval_results,
        merged_results=existing_merged_results,
    )
    write_evaluation_queue(evaluation_queue, "reports/evaluation_queue.json")
    print_queue_summary(evaluation_queue)

    force_evaluation_prompts = os.getenv("FORCE_EVALUATION_PROMPTS", "").strip().lower() in {"1", "true", "yes"}
    prompt_jobs = pending_jobs_from_queue(
        evaluation_queue,
        evaluator_jobs_by_id,
        force=force_evaluation_prompts,
    )
    export_evaluation_prompts(
        prompt_jobs,
        build_evaluation_prompt,
        "reports/evaluation_prompts.md",
        shared_prompt=build_evaluation_prompt_preamble(),
    )

    # Run the evaluator results ingestion & final report generation
    try:
        run_final_report()
    except Exception as e:
        print(f"Final report generation failed: {e}")
        raise

    daily_candidates = detail_keep + detail_maybe

    build_daily_report(daily_candidates)

if __name__ == "__main__":
    main()
