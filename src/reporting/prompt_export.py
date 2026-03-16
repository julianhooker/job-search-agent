from pathlib import Path

def export_evaluation_prompts(jobs, build_prompt_fn, filename="reports/evaluation_prompts.md"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Job Evaluation Prompts", ""]

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

        lines.append(f"## {index}. {title} — {company}")
        lines.append("")
        lines.append(f"- Job ID: `{job_id}`")
        lines.append(f"- URL: {url}")
        lines.append("")

        lines.append("```text")
        lines.append(prompt)
        lines.append("```")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {len(jobs)} evaluation prompts to {filename}")