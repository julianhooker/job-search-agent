from src.collectors.common import build_base_job_record, fetch_json, normalize_text


def collect_greenhouse_jobs(company_url, company_name=None):
    """
    Collect published jobs from a Greenhouse board using the Greenhouse Job Board API.
    Example company_url:
      https://job-boards.greenhouse.io/gitlab
    """

    company_slug = company_url.rstrip("/").split("/")[-1]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"

    data = fetch_json(api_url)

    jobs = []

    for job in data.get("jobs", []):
        location_obj = job.get("location") or {}
        metadata = job.get("metadata") or []

        location = location_obj.get("name", "") or ""

        # Sometimes additional location-ish details can appear in metadata
        metadata_text = []
        for item in metadata:
            name = item.get("name", "")
            value = item.get("value", "")
            if name or value:
                metadata_text.append(f"{name}: {value}".strip(": "))

        external_id = job.get("id")
        jobs.append(
            build_base_job_record(
                "greenhouse",
                company_slug,
                external_id,
                title=job.get("title", ""),
                location=location,
                url=job.get("absolute_url", ""),
                company=company_name or "",
                updated_at=normalize_text(job.get("updated_at", "")),
                metadata=normalize_text(" | ".join(metadata_text)),
            )
        )

    return jobs
