REPORTS_DIR = "reports"

# User-facing files kept at the reports root.
DAILY_JOB_REPORT = f"{REPORTS_DIR}/daily_job_report.md"
EVALUATION_BATCH_PROMPT = f"{REPORTS_DIR}/evaluation_batch_prompt.md"
EVALUATION_PROMPTS = f"{REPORTS_DIR}/evaluation_prompts.md"
EVALUATOR_RESULTS = f"{REPORTS_DIR}/evaluator_results.json"
FINAL_RECOMMENDATIONS = f"{REPORTS_DIR}/final_recommendations.md"

# Internal/generated pipeline files grouped into subfolders.
DATA_DIR = f"{REPORTS_DIR}/data"
STATE_DIR = f"{REPORTS_DIR}/state"

JOBS_KEEP_CSV = f"{DATA_DIR}/jobs_keep.csv"
JOBS_MAYBE_CSV = f"{DATA_DIR}/jobs_maybe.csv"
JOBS_REJECTED_CSV = f"{DATA_DIR}/jobs_rejected.csv"
JOBS_REVIEW_JSON = f"{DATA_DIR}/jobs_review.json"

JOBS_DETAIL_KEEP_CSV = f"{DATA_DIR}/jobs_detail_keep.csv"
JOBS_DETAIL_MAYBE_CSV = f"{DATA_DIR}/jobs_detail_maybe.csv"
JOBS_DETAIL_REJECT_CSV = f"{DATA_DIR}/jobs_detail_reject.csv"
JOBS_DETAIL_REVIEW_JSON = f"{DATA_DIR}/jobs_detail_review.json"

EVALUATION_QUEUE_JSON = f"{STATE_DIR}/evaluation_queue.json"
EVALUATOR_RESULTS_MERGED = f"{STATE_DIR}/evaluator_results_merged.json"
