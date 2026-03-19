from pathlib import Path

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
