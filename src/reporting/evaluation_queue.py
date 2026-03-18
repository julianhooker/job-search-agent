import argparse
import json
from pathlib import Path


QUEUE_STATUSES = {"pending", "evaluated", "merged", "skipped"}


def load_json_file(path):
    p = Path(path)
    if not p.exists():
        return []

    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def summarize_queue(queue_items):
    counts = {status: 0 for status in QUEUE_STATUSES}
    for item in queue_items:
        status = item.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = len(queue_items)
    return counts


def build_evaluation_queue(candidate_jobs, skipped_jobs=None, eval_results=None, merged_results=None):
    skipped_jobs = skipped_jobs or []
    eval_results = eval_results or []
    merged_results = merged_results or []

    evaluated_ids = {
        str(item.get("job_id")).strip()
        for item in eval_results
        if isinstance(item, dict) and item.get("job_id")
    }
    merged_ids = {
        str(item.get("job_id")).strip()
        for item in merged_results
        if isinstance(item, dict) and item.get("job_id")
    }

    queue_items = []

    for job in candidate_jobs:
        job_id = job.get("job_id")
        status = "pending"
        if job_id in merged_ids:
            status = "merged"
        elif job_id in evaluated_ids:
            status = "evaluated"

        queue_items.append(
            {
                "job_id": job_id,
                "status": status,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "url": job.get("url", ""),
                "location": job.get("location", ""),
                "detail_status": job.get("detail_status", ""),
                "detail_reasons": job.get("detail_reasons", ""),
                "ready_for_evaluation": status == "pending",
            }
        )

    for job in skipped_jobs:
        queue_items.append(
            {
                "job_id": job.get("job_id"),
                "status": "skipped",
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "url": job.get("url", ""),
                "location": job.get("location", ""),
                "detail_status": job.get("detail_status", ""),
                "detail_reasons": job.get("detail_reasons", ""),
                "ready_for_evaluation": False,
            }
        )

    queue_items.sort(
        key=lambda item: (
            ["pending", "evaluated", "merged", "skipped"].index(item.get("status", "pending")),
            (item.get("company") or "").lower(),
            (item.get("title") or "").lower(),
        )
    )
    return queue_items


def write_evaluation_queue(queue_items, filename="reports/evaluation_queue.json"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(queue_items, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(queue_items)} evaluation queue entries to {filename}")


def pending_jobs_from_queue(queue_items, candidate_jobs_by_id, force=False):
    if force:
        return list(candidate_jobs_by_id.values())

    pending_ids = [item.get("job_id") for item in queue_items if item.get("status") == "pending"]
    return [candidate_jobs_by_id[job_id] for job_id in pending_ids if job_id in candidate_jobs_by_id]


def print_queue_summary(queue_items):
    counts = summarize_queue(queue_items)
    print("Evaluation queue summary:")
    print(f"- Total: {counts['total']}")
    print(f"- Pending: {counts.get('pending', 0)}")
    print(f"- Evaluated: {counts.get('evaluated', 0)}")
    print(f"- Merged: {counts.get('merged', 0)}")
    print(f"- Skipped: {counts.get('skipped', 0)}")


def generate_queue_from_reports(
    review_file="reports/jobs_detail_review.json",
    eval_file="reports/evaluator_results.json",
    merged_file="reports/evaluator_results_merged.json",
    output_file="reports/evaluation_queue.json",
):
    review_jobs = load_json_file(review_file)
    eval_results = load_json_file(eval_file)
    merged_results = load_json_file(merged_file)

    if not isinstance(review_jobs, list):
        raise ValueError(f"Review file must contain a JSON array: {review_file}")

    candidate_jobs = [
        job for job in review_jobs
        if str(job.get("detail_status") or "").strip().lower() in {"keep", "maybe"}
    ]
    skipped_jobs = [
        job for job in review_jobs
        if str(job.get("detail_status") or "").strip().lower() not in {"keep", "maybe"}
    ]

    queue_items = build_evaluation_queue(
        candidate_jobs=candidate_jobs,
        skipped_jobs=skipped_jobs,
        eval_results=eval_results,
        merged_results=merged_results,
    )
    write_evaluation_queue(queue_items, output_file)
    return queue_items


def main():
    parser = argparse.ArgumentParser(description="Print summary counts for the manual evaluation queue.")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Regenerate the queue from existing report JSON files before printing the summary",
    )
    parser.add_argument(
        "--queue-file",
        default="reports/evaluation_queue.json",
        help="Path to the evaluation queue JSON file",
    )
    parser.add_argument("--review-file", default="reports/jobs_detail_review.json", help="Path to detail review jobs JSON")
    parser.add_argument("--eval-file", default="reports/evaluator_results.json", help="Path to evaluator results JSON")
    parser.add_argument(
        "--merged-file",
        default="reports/evaluator_results_merged.json",
        help="Path to merged evaluator results JSON",
    )
    args = parser.parse_args()

    if args.generate:
        queue_items = generate_queue_from_reports(
            review_file=args.review_file,
            eval_file=args.eval_file,
            merged_file=args.merged_file,
            output_file=args.queue_file,
        )
    else:
        queue_items = load_json_file(args.queue_file)
        if not isinstance(queue_items, list):
            raise ValueError(f"Queue file must contain a JSON array: {args.queue_file}")

    print_queue_summary(queue_items)


if __name__ == "__main__":
    main()
