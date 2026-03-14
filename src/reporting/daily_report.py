from pathlib import Path


def build_daily_report(jobs, filename="reports/daily_job_report.md"):

    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Daily Job Report")
    lines.append("")

    if not jobs:
        lines.append("No jobs matched your filters today.")
        path.write_text("\n".join(lines))
        return

    for job in jobs:

        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company")
        url = job.get("url", "")
        salary = job.get("salary_text", "Not listed")
        location = job.get("location", "")
        status = job.get("detail_status", "")
        reasons = job.get("detail_reasons", "")

        lines.append(f"## {title} — {company}")
        lines.append("")
        lines.append(f"Location: {location}")
        lines.append(f"Salary: {salary}")
        lines.append(f"Status: {status}")
        lines.append(f"Reasons: {reasons}")
        lines.append("")
        lines.append(url)
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines))