import requests


def collect_greenhouse_jobs(company_url):
    """
    Collect published jobs from a Greenhouse board using the Greenhouse Job Board API.
    Example company_url:
      https://job-boards.greenhouse.io/gitlab
    """

    company_slug = company_url.rstrip("/").split("/")[-1]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"

    response = requests.get(api_url, timeout=30)
    response.raise_for_status()
    data = response.json()

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

        jobs.append({
            "title": job.get("title", "").strip(),
            "location": location.strip(),
            "url": job.get("absolute_url", "").strip(),
            "internal_job_id": job.get("id"),
            "updated_at": job.get("updated_at", ""),
            "metadata": " | ".join(metadata_text),
        })

    return jobs