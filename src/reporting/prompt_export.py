import json
from pathlib import Path
import re

from src.evaluators.job_evaluator import (
    CANONICAL_EVALUATOR_RESULT_SCHEMA,
    EVALUATION_INSTRUCTIONS,
    USER_PROFILE,
    build_job_payload,
)

def export_evaluation_prompts(jobs, build_prompt_fn, filename="reports/evaluation_prompts.md", shared_prompt=None):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Job Evaluation Prompts", ""]

    if shared_prompt:
        lines.extend(
            [
                "## Shared Instructions",
                "",
                "Copy this section once per manual LLM session, then paste one or more job blocks below.",
                "",
                "```text",
                shared_prompt,
                "```",
                "",
                "---",
                "",
            ]
        )

    for index, job in enumerate(jobs, start=1):
        job_id = job.get("job_id")
        if not job_id:
            raise ValueError(
                f"Job at index {index} is missing job_id: "
                f"title={job.get('title')!r}, company={job.get('company')!r}"
            )

        title = job.get("title", "Untitled Job")
        company = job.get("company", "Unknown Company")
        url = job.get("url", "")

        prompt = build_prompt_fn(job)

        lines.append(f"## {index}. [{job_id}] {company} | {title}")
        lines.append("")
        lines.append(f"- `job_id`: `{job_id}`")
        lines.append(f"- Company/Title: {company} | {title}")
        if url:
            lines.append(f"- URL: {url}")
        lines.append("")

        lines.append("```text")
        lines.append(prompt)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {len(jobs)} evaluation prompts to {filename}")


def _build_batch_prompt_text(jobs):
    jobs_payload = [build_job_payload(job) for job in jobs]
    return "\n".join(
        [
            "Evaluate the following jobs for the candidate.",
            "",
            USER_PROFILE,
            "",
            EVALUATION_INSTRUCTIONS,
            "",
            "For this batch request, override the single-job output instruction above.",
            "Return ONLY a JSON array. Each element must follow this schema:",
            CANONICAL_EVALUATOR_RESULT_SCHEMA,
            "",
            "Every array element must include all required fields above.",
            "Use explicit `unknown` or `ambiguous` values instead of omitting assessment keys.",
            "",
            "Jobs:",
            json.dumps(jobs_payload, indent=2),
        ]
    )


def _batch_prompt_markdown(batch_prompt, heading="# Batch Job Evaluation Prompt", description=None):
    if description is None:
        description = "Copy the prompt below into your LLM to evaluate all jobs at once."

    return [
        heading,
        "",
        description,
        "",
        "```text",
        batch_prompt,
        "```",
        "",
    ]


def _company_slug(company_name):
    slug = re.sub(r"[^a-z0-9]+", "_", company_name.lower()).strip("_")
    return slug or "unknown_company"


def export_batch_evaluation_prompt(jobs, filename="reports/evaluation_batch_prompt.md"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    batch_prompt = _build_batch_prompt_text(jobs)
    lines = _batch_prompt_markdown(batch_prompt)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved batch evaluation prompt to {filename}")


def export_batch_evaluation_prompts_by_company(jobs, output_dir="reports"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    jobs_by_company = {}
    for job in jobs:
        company = job.get("company", "Unknown Company")
        jobs_by_company.setdefault(company, []).append(job)

    for company, company_jobs in sorted(jobs_by_company.items()):
        slug = _company_slug(company)
        filename = output_path / f"evaluation_batch_prompt_{slug}.md"
        batch_prompt = _build_batch_prompt_text(company_jobs)
        lines = _batch_prompt_markdown(
            batch_prompt,
            heading=f"# Batch Job Evaluation Prompt: {company}",
            description=f"Copy the prompt below into your LLM to evaluate the current {company} jobs as one batch.",
        )
        filename.write_text("\n".join(lines), encoding="utf-8")
        print(f"Saved {len(company_jobs)} {company} batch jobs to {filename}")
