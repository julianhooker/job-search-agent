import os
from pathlib import Path

from src.evaluators.job_evaluator import (
    CANONICAL_EVALUATOR_RESULT_SCHEMA,
    EVALUATION_INSTRUCTIONS,
    USER_PROFILE,
    build_job_payload,
)
from src.utils.config_loader import load_settings

DEFAULT_PROMPT_BATCH_SIZE = 4
DEFAULT_PROMPT_MAX_CHARS = 12000


def _read_positive_int_env(name, default):
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer; got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"Environment variable {name} must be > 0; got {value}")
    return value


def prompt_batch_config_from_env():
    settings = load_settings()
    evaluation_prompt_settings = settings.get("evaluation_prompts", {})
    configured_batch_size = int(evaluation_prompt_settings.get("batch_size", DEFAULT_PROMPT_BATCH_SIZE))
    configured_max_chars = int(evaluation_prompt_settings.get("max_chars", DEFAULT_PROMPT_MAX_CHARS))

    if configured_batch_size <= 0:
        raise ValueError("config/settings.yaml evaluation_prompts.batch_size must be > 0")
    if configured_max_chars <= 0:
        raise ValueError("config/settings.yaml evaluation_prompts.max_chars must be > 0")

    return {
        "max_jobs_per_batch": _read_positive_int_env(
            "EVALUATION_PROMPT_BATCH_SIZE",
            configured_batch_size,
        ),
        "max_chars_per_batch": _read_positive_int_env(
            "EVALUATION_PROMPT_MAX_CHARS",
            configured_max_chars,
        ),
    }


def _batch_header_lines(batch_name, jobs_count, total_batches, max_jobs_per_batch, max_chars_per_batch):
    return [
        f"# Evaluation Prompt {batch_name}",
        "",
        f"Batch {batch_name} of {total_batches}. Copy the full code block below into your evaluator chat.",
        f"This batch contains {jobs_count} job(s). Config: max {max_jobs_per_batch} jobs per batch, max {max_chars_per_batch} chars per batch.",
        "",
    ]


def _build_batch_prompt_text(rendered_job_payloads, batch_name, total_batches):
    return "\n".join(
        [
            f"BATCH_ID: {batch_name}",
            f"BATCH_SIZE: {len(rendered_job_payloads)}",
            f"BATCH_POSITION: {batch_name} of {total_batches}",
            "",
            "Evaluate the following jobs for the candidate.",
            "",
            USER_PROFILE,
            "",
            EVALUATION_INSTRUCTIONS,
            "",
            "For this batch request, return ONLY a JSON array.",
            "Each array element must follow this exact schema:",
            CANONICAL_EVALUATOR_RESULT_SCHEMA,
            "",
            "Rules for this batch:",
            "- Return one object per job.",
            "- Preserve every job_id exactly as given.",
            "- Do not omit required fields.",
            "- Use `unknown` or `ambiguous` rather than dropping assessment keys.",
            "",
            "Jobs:",
            "",
            *[
                "\n".join(
                    [
                        f"Job {index}:",
                        rendered_job_payload,
                        "",
                    ]
                ).rstrip()
                for index, rendered_job_payload in enumerate(rendered_job_payloads, start=1)
            ],
        ]
    )


def _render_job_payload(job):
    payload = build_job_payload(job)
    lines = []
    field_order = [
        "job_id",
        "company",
        "title",
        "location",
        "workplace_type",
        "salary_text",
        "salary_min",
        "salary_max",
        "travel_text",
        "mentions_travel",
        "mentions_after_hours",
        "mentions_weekends",
        "mentions_on_call",
        "manager_scope",
        "prefilter_status",
        "prefilter_reasons",
        "detail_status",
        "detail_reasons",
        "description_excerpt",
        "url",
    ]

    for field in field_order:
        if field not in payload:
            continue
        value = payload[field]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        lines.append(f"{field}: {rendered}")

    return "\n".join(lines)


def _estimate_batch_chars(rendered_jobs, batch_name, total_batches):
    return len(_build_batch_prompt_text(rendered_jobs, batch_name=batch_name, total_batches=total_batches))


def batch_jobs_for_prompts(jobs, max_jobs_per_batch=DEFAULT_PROMPT_BATCH_SIZE, max_chars_per_batch=DEFAULT_PROMPT_MAX_CHARS):
    if max_jobs_per_batch <= 0:
        raise ValueError("max_jobs_per_batch must be > 0")
    if max_chars_per_batch <= 0:
        raise ValueError("max_chars_per_batch must be > 0")

    rendered_jobs = [{"job": job, "payload": _render_job_payload(job)} for job in jobs]
    if not rendered_jobs:
        return []

    batches = []
    current_batch = []
    estimated_total_batches = max(1, (len(rendered_jobs) + max_jobs_per_batch - 1) // max_jobs_per_batch)

    for rendered_job in rendered_jobs:
        candidate_batch = current_batch + [rendered_job]
        projected_chars = _estimate_batch_chars(
            [item["payload"] for item in candidate_batch],
            batch_name=f"batch_{len(batches) + 1:03d}",
            total_batches=estimated_total_batches,
        )

        if current_batch and (
            len(candidate_batch) > max_jobs_per_batch or projected_chars > max_chars_per_batch
        ):
            batches.append(current_batch)
            current_batch = [rendered_job]
            continue

        current_batch = candidate_batch

    if current_batch:
        batches.append(current_batch)

    return [[item["job"] for item in batch] for batch in batches]


def _write_batch_file(batch_jobs, batch_path, batch_name, total_batches, max_jobs_per_batch, max_chars_per_batch):
    batch_prompt = _build_batch_prompt_text(
        [_render_job_payload(job) for job in batch_jobs],
        batch_name=batch_name,
        total_batches=total_batches,
    )

    lines = _batch_header_lines(
        batch_name=batch_name,
        jobs_count=len(batch_jobs),
        total_batches=total_batches,
        max_jobs_per_batch=max_jobs_per_batch,
        max_chars_per_batch=max_chars_per_batch,
    )
    lines.extend(
        [
            "```text",
            batch_prompt,
            "```",
            "",
        ]
    )
    batch_path.write_text("\n".join(lines), encoding="utf-8")


def _write_prompt_index(index_path, prompt_dir, batches, max_jobs_per_batch, max_chars_per_batch):
    lines = [
        "# Evaluation Prompt Batches",
        "",
        f"Prompt batches are written to `{prompt_dir}`.",
        f"Default configuration is {max_jobs_per_batch} job(s) per batch and {max_chars_per_batch} chars per batch.",
        "Each batch is self-contained: copy one batch file at a time into your evaluator chat.",
        "Append the returned JSON objects into `reports/evaluator_results.json` as a single valid JSON array.",
        "",
        "## Generated Batches",
        "",
    ]

    if not batches:
        lines.append("No pending jobs require manual evaluation.")
    else:
        for index, batch_jobs in enumerate(batches, start=1):
            batch_name = f"batch_{index:03d}.md"
            job_ids = ", ".join(job.get("job_id", "missing-job-id") for job in batch_jobs)
            lines.append(f"- `{batch_name}`: {len(batch_jobs)} job(s) [{job_ids}]")

    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append("- `EVALUATION_PROMPT_BATCH_SIZE`: max jobs per batch")
    lines.append("- `EVALUATION_PROMPT_MAX_CHARS`: approximate max characters per batch")
    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")


def export_evaluation_prompts(
    jobs,
    prompt_dir="reports/evaluation_prompts",
    index_filename="reports/evaluation_prompts.md",
    max_jobs_per_batch=None,
    max_chars_per_batch=None,
):
    config = prompt_batch_config_from_env()
    if max_jobs_per_batch is None:
        max_jobs_per_batch = config["max_jobs_per_batch"]
    if max_chars_per_batch is None:
        max_chars_per_batch = config["max_chars_per_batch"]

    prompt_path = Path(prompt_dir)
    prompt_path.mkdir(parents=True, exist_ok=True)
    for existing_file in prompt_path.glob("batch_*.md"):
        existing_file.unlink()

    batches = batch_jobs_for_prompts(
        jobs,
        max_jobs_per_batch=max_jobs_per_batch,
        max_chars_per_batch=max_chars_per_batch,
    )
    total_batches = max(1, len(batches))

    written_files = []
    for index, batch_jobs in enumerate(batches, start=1):
        batch_name = f"batch_{index:03d}"
        batch_path = prompt_path / f"{batch_name}.md"
        _write_batch_file(
            batch_jobs,
            batch_path,
            batch_name=batch_name,
            total_batches=total_batches,
            max_jobs_per_batch=max_jobs_per_batch,
            max_chars_per_batch=max_chars_per_batch,
        )
        written_files.append(str(batch_path))

    _write_prompt_index(
        Path(index_filename),
        prompt_dir,
        batches,
        max_jobs_per_batch=max_jobs_per_batch,
        max_chars_per_batch=max_chars_per_batch,
    )
    print(f"Saved {len(written_files)} evaluation prompt batch file(s) to {prompt_dir}")
    print(f"Saved evaluation prompt index to {index_filename}")
    return written_files


def export_batch_evaluation_prompt(jobs, filename="reports/evaluation_batch_prompt.md"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Evaluation Batch Prompt",
        "",
        "This file is deprecated in favor of smaller prompt batches.",
        "Use `reports/evaluation_prompts/` and copy one `batch_###.md` file at a time.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote batch prompt notice to {filename}")


def export_batch_evaluation_prompts_by_company(jobs, output_dir="reports"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Evaluation Batch Prompt Files By Company",
        "",
        "Per-company monolithic batch prompts are deprecated in favor of smaller prompt batches.",
        "Use `reports/evaluation_prompts/` and process one `batch_###.md` file at a time.",
        "",
    ]
    notice_path = output_path / "evaluation_batch_prompt_by_company.md"
    notice_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote company batch prompt notice to {notice_path}")
