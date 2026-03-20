from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import requests

from src.collectors.common import (
    build_base_job_record,
    fetch_json,
    log_collector_event,
    normalize_text,
)


def _resolve_lever_api_url(company_url):
    parsed = urlparse(company_url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in {"jobs.lever.co", "jobs.eu.lever.co"}:
        if not path_parts:
            raise ValueError(f"Lever URL is missing company slug: {company_url}")

        company_slug = path_parts[0]
        api_host = "api.eu.lever.co" if host == "jobs.eu.lever.co" else "api.lever.co"
        api_path = f"/v0/postings/{company_slug}"
        query = urlencode({"mode": "json"})
        api_url = urlunparse(("https", api_host, api_path, "", query, ""))
        return company_slug, api_url

    if host in {"api.lever.co", "api.eu.lever.co"} and len(path_parts) >= 3 and path_parts[:2] == ["v0", "postings"]:
        company_slug = path_parts[2]
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        query_params["mode"] = ["json"]
        api_url = urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                f"/v0/postings/{company_slug}",
                "",
                urlencode(query_params, doseq=True),
                "",
            )
        )
        return company_slug, api_url

    raise ValueError(
        "Unsupported Lever URL format. Expected jobs.lever.co/<company>, jobs.eu.lever.co/<company>, "
        "or api.lever.co/v0/postings/<company>."
    )


def _normalize_employment_type(commitment):
    text = normalize_text(commitment).lower()
    mapping = {
        "fulltime": "Full-time",
        "full-time": "Full-time",
        "full time": "Full-time",
        "parttime": "Part-time",
        "part-time": "Part-time",
        "part time": "Part-time",
        "intern": "Intern",
        "internship": "Intern",
        "contract": "Contract",
        "contractor": "Contract",
        "temporary": "Temporary",
        "temp": "Temporary",
    }
    return mapping.get(text, normalize_text(commitment))


def _extract_travel_text(*text_blocks):
    lines = []
    for block in text_blocks:
        for raw_line in normalize_text(block).splitlines():
            line = raw_line.strip()
            if line and "travel" in line.lower():
                lines.append(line)
    return " | ".join(lines[:3])


def _build_location(categories, workplace_type):
    primary_location = normalize_text((categories or {}).get("location"))
    all_locations = [normalize_text(item) for item in (categories or {}).get("allLocations", []) if normalize_text(item)]
    normalized_workplace = normalize_text(workplace_type).lower()

    if normalized_workplace == "remote":
        if primary_location and "remote" not in primary_location.lower():
            return f"Remote, {primary_location}"
        if all_locations and "remote" not in all_locations[0].lower():
            return f"Remote, {all_locations[0]}"
        return primary_location or "Remote"

    if normalized_workplace == "hybrid":
        if primary_location:
            return f"Hybrid, {primary_location}"
        return "Hybrid"

    if primary_location:
        return primary_location

    if all_locations:
        return all_locations[0]

    return ""


def _build_metadata(categories, workplace_type):
    categories = categories or {}
    metadata_parts = []

    for label, value in (
        ("team", categories.get("team")),
        ("department", categories.get("department")),
        ("commitment", categories.get("commitment")),
        ("workplace_type", workplace_type),
    ):
        normalized_value = normalize_text(value)
        if normalized_value:
            metadata_parts.append(f"{label}: {normalized_value}")

    all_locations = [normalize_text(item) for item in categories.get("allLocations", []) if normalize_text(item)]
    if all_locations:
        metadata_parts.append(f"all_locations: {', '.join(all_locations)}")

    return " | ".join(metadata_parts)


def collect_lever_jobs(company_url, company_name=None):
    """
    Collect published jobs from a Lever board using the public Lever postings API.

    Supported URL forms:
    - https://jobs.lever.co/<company_slug>
    - https://jobs.eu.lever.co/<company_slug>
    - https://api.lever.co/v0/postings/<company_slug>?mode=json
    """

    company_slug, api_url = _resolve_lever_api_url(company_url)
    try:
        postings = fetch_json(api_url)
    except requests.RequestException as exc:
        log_collector_event(
            "lever",
            f"Fetch failed for company_slug={company_slug} api_url={api_url}: {exc}",
            level="ERROR",
        )
        raise RuntimeError(f"Failed to fetch Lever postings for {company_slug} from {api_url}") from exc

    if not isinstance(postings, list):
        raise ValueError(f"Lever API returned unexpected payload for {company_slug}: expected list")

    jobs = []
    skipped_count = 0

    for index, posting in enumerate(postings, start=1):
        external_id = posting.get("id")
        title = normalize_text(posting.get("text"))
        hosted_url = normalize_text(posting.get("hostedUrl"))

        if not external_id or not title or not hosted_url:
            skipped_count += 1
            log_collector_event(
                "lever",
                (
                    f"Skipping malformed posting #{index} for {company_slug}: "
                    f"id={external_id!r}, title={title!r}, hostedUrl={hosted_url!r}"
                ),
                level="WARN",
            )
            continue

        categories = posting.get("categories") or {}
        workplace_type = normalize_text(posting.get("workplaceType"))
        commitment = categories.get("commitment") or ""
        salary_range = posting.get("salaryRange") or {}
        salary_description = normalize_text(posting.get("salaryDescriptionPlain"))

        salary_min = salary_range.get("min")
        salary_max = salary_range.get("max")
        salary_currency = normalize_text(salary_range.get("currency"))
        salary_interval = normalize_text(salary_range.get("interval"))

        salary_parts = []
        if salary_min is not None or salary_max is not None:
            if salary_currency:
                salary_parts.append(salary_currency)
            if salary_min is not None and salary_max is not None:
                salary_parts.append(f"{salary_min}-{salary_max}")
            elif salary_min is not None:
                salary_parts.append(f"min {salary_min}")
            elif salary_max is not None:
                salary_parts.append(f"max {salary_max}")
            if salary_interval:
                salary_parts.append(salary_interval)
        salary_text = " ".join(part for part in salary_parts if part).strip()
        if salary_description:
            salary_text = f"{salary_text} | {salary_description}".strip(" |") if salary_text else salary_description

        description_plain = normalize_text(posting.get("descriptionPlain"))
        additional_plain = normalize_text(posting.get("additionalPlain"))
        travel_text = _extract_travel_text(description_plain, additional_plain)
        description_text = "\n\n".join(part for part in (description_plain, additional_plain) if part)

        jobs.append(
            build_base_job_record(
                "lever",
                company_slug,
                external_id,
                title=title,
                location=_build_location(categories, workplace_type),
                url=hosted_url,
                company=company_name or "",
                metadata=_build_metadata(categories, workplace_type),
                employment_type=_normalize_employment_type(commitment),
                travel_text=travel_text,
                mentions_travel=bool(travel_text),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_text=salary_text,
                description_text=description_text,
                workplace_type=workplace_type,
                updated_at="",
            )
        )

    missing_location_count = sum(1 for job in jobs if not normalize_text(job.get("location")))
    missing_employment_type_count = sum(1 for job in jobs if not normalize_text(job.get("employment_type")))
    missing_salary_count = sum(1 for job in jobs if job.get("salary_min") is None and job.get("salary_max") is None)

    if skipped_count:
        log_collector_event(
            "lever",
            f"Collected {len(jobs)} jobs from {company_slug}; skipped {skipped_count} malformed posting(s)",
            level="WARN",
        )
    else:
        log_collector_event("lever", f"Collected {len(jobs)} jobs from {company_slug}")

    log_collector_event(
        "lever",
        (
            f"Diagnostics for {company_slug}: "
            f"missing_location={missing_location_count}, "
            f"missing_employment_type={missing_employment_type_count}, "
            f"missing_salary={missing_salary_count}"
        ),
    )

    return jobs
