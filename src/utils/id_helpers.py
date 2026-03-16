def build_job_id(source, company_slug, external_id):
    return f"{source}:{company_slug}:{external_id}"


def require_job_ids(jobs, stage_name="unknown"):
    missing = []
    for index, job in enumerate(jobs, start=1):
        if not job.get("job_id") or not job.get("source") or not job.get("company_slug") or not job.get("external_job_id"):
            missing.append((index, job.get("title"), job.get("company")))

    if missing:
        samples = ", ".join([f"index={i},title={t!r},company={c!r}" for i, t, c in missing[:5]])
        raise ValueError(f"Stage '{stage_name}' found {len(missing)} job(s) missing identity fields. Examples: {samples}")

    return True
