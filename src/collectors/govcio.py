import html
import re
import time
from math import ceil
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.collectors.common import (
    build_base_job_record,
    build_retry_session,
    log_collector_event,
    normalize_text,
)


LIST_API_URL = "https://careers.govcio.com/api/jobs"
DETAIL_API_URL_TEMPLATE = "https://careers.govcio.com/api/jobs/{slug}/{language}"
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 50
DETAIL_REQUEST_DELAY_SECONDS = 0.1
PREFERRED_REMOTE_TAG = "Fully remote"
PREFERRED_CATEGORIES = {
    "Information Technology",
    "Software Engineering Services",
    "Other",
}


def _normalize_employment_type(value):
    text = normalize_text(value).lower().replace("_", " ").replace("-", " ")
    mapping = {
        "full time": "Full-time",
        "part time": "Part-time",
        "contract": "Contract",
        "temporary": "Temporary",
        "intern": "Intern",
        "internship": "Intern",
    }
    return mapping.get(text, normalize_text(value))


def _normalize_category_names(detail):
    return [
        normalize_text(item.get("name"))
        for item in detail.get("categories") or []
        if normalize_text(item.get("name"))
    ]


def _normalize_workplace_type(tags):
    if not tags:
        return ""

    text = normalize_text(tags[0]).lower()
    mapping = {
        "fully remote": "remote",
        "hybrid schedule": "hybrid",
        "on-site only": "onsite",
        "flexible for occasional remote work": "hybrid",
    }
    return mapping.get(text, text.replace(" ", "_"))


def _build_location(detail):
    short_location = normalize_text(detail.get("short_location"))
    city = normalize_text(detail.get("city"))
    state = normalize_text(detail.get("state"))
    country = normalize_text(detail.get("country"))
    workplace_type = _normalize_workplace_type(detail.get("tags2") or [])

    if short_location:
        location = short_location
    else:
        location_parts = [part for part in (city, state, country) if part]
        location = ", ".join(location_parts)

    if workplace_type == "remote":
        if location and "remote" not in location.lower():
            return f"Remote, {location}"
        return location or "Remote"

    if workplace_type == "hybrid":
        if location and "hybrid" not in location.lower():
            return f"Hybrid, {location}"
        return location or "Hybrid"

    return location


def _extract_text_lines_from_html(html_fragment):
    if not html_fragment:
        return []

    soup = BeautifulSoup(html_fragment, "html.parser")

    for tag in soup.find_all("br"):
        tag.replace_with("\n")

    lines = []
    block_tags = {"p", "div", "section", "article", "ul", "ol"}
    item_tags = {"li"}
    heading_tags = {"strong", "h1", "h2", "h3", "h4", "h5", "h6"}

    for element in soup.find_all(block_tags | item_tags | heading_tags):
        text = element.get_text(" ", strip=True)
        if not text:
            continue

        if element.name in item_tags:
            lines.append(f"- {text}")
            continue

        if element.name in heading_tags:
            if len(text) <= 120:
                lines.append(text)
            continue

        lines.extend(part.strip() for part in text.splitlines() if part.strip())

    if lines:
        return _dedupe_adjacent_lines(lines)

    text = soup.get_text("\n", strip=True)
    return _dedupe_adjacent_lines([line.strip() for line in text.splitlines() if line.strip()])


def _dedupe_adjacent_lines(lines):
    deduped = []
    previous = None
    for line in lines:
        normalized = normalize_text(line)
        if normalized and normalized != previous:
            deduped.append(line)
            previous = normalized
    return deduped


def _clean_description_text(*html_fragments):
    combined_lines = []
    for fragment in html_fragments:
        combined_lines.extend(_extract_text_lines_from_html(fragment))

    cleaned_lines = []
    seen = set()

    stop_heading_markers = (
        "company overview",
        "what you can expect",
        "interview & hiring process",
        "employee perks",
        "equal opportunity employer",
    )

    for line in combined_lines:
        normalized = normalize_text(html.unescape(line))
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned_lines.append(re.sub(r"\s+", " ", html.unescape(line)).strip())
        if any(normalized.startswith(marker) for marker in stop_heading_markers):
            break

    text = "\n".join(cleaned_lines).strip()
    cutoff_pattern = re.compile(
        r"(?im)^(company overview|what you can expect|interview & hiring process|employee perks|equal opportunity employer).*$"
    )
    match = cutoff_pattern.search(text)
    if match:
        return text[: match.end()].strip()
    return text


def _extract_salary_fields(description_text):
    text = normalize_text(description_text)
    if not text:
        return "", None, None

    patterns = [
        re.compile(
            r"(?:pay range|posted salary range)\s*:\s*(usd\s*\$?[\d,]+(?:\.\d+)?)\s*-\s*(usd\s*\$?[\d,]+(?:\.\d+)?)\s*/\s*(yr|year|annually|hr|hour)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(usd\s*\$?[\d,]+(?:\.\d+)?)\s*-\s*(usd\s*\$?[\d,]+(?:\.\d+)?)\s*/\s*(yr|year|annually|hr|hour)",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        match = pattern.search(description_text)
        if not match:
            continue

        raw_min, raw_max, interval = match.groups()
        salary_text = match.group(0).strip()

        interval = interval.lower()
        if interval in {"yr", "year", "annually"}:
            salary_min = int(float(re.sub(r"[^\d.]", "", raw_min)))
            salary_max = int(float(re.sub(r"[^\d.]", "", raw_max)))
            return salary_text, salary_min, salary_max

        return salary_text, None, None

    return "", None, None


def _extract_travel_text(description_text):
    matches = []
    for raw_line in description_text.splitlines():
        line = raw_line.strip()
        if line and "travel" in line.lower():
            matches.append(line)
    return " | ".join(matches[:3])


def _extract_manager_scope(description_text):
    match = re.search(
        r"(\d+\+?\s*(?:direct reports|engineers|people|team members))",
        description_text,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _build_metadata(detail):
    metadata_parts = []

    category_names = _normalize_category_names(detail)
    if category_names:
        metadata_parts.append(f"category: {', '.join(category_names)}")

    department = normalize_text(detail.get("department"))
    if department:
        metadata_parts.append(f"department: {department}")

    remote_status = normalize_text((detail.get("tags2") or [""])[0])
    if remote_status:
        metadata_parts.append(f"remote_status: {remote_status}")

    clearance = normalize_text((detail.get("tags1") or [""])[0])
    if clearance:
        metadata_parts.append(f"clearance: {clearance}")

    employment_type = _normalize_employment_type(detail.get("employment_type"))
    if employment_type:
        metadata_parts.append(f"employment_type: {employment_type}")

    return " | ".join(metadata_parts)


def _infer_public_job_url(detail):
    meta_data = detail.get("meta_data") or {}
    for key in ("job_description_url", "public_url", "source_url"):
        value = normalize_text(meta_data.get(key))
        if value and "govcio.com/jobs/" in value:
            return value

    nested_icims = meta_data.get("icims") or {}
    for key in ("job_description_url", "public_url", "source_url"):
        value = normalize_text(nested_icims.get(key))
        if value and "govcio.com/jobs/" in value:
            return value

    return ""


def _canonical_job_url(detail):
    public_url = _infer_public_job_url(detail)
    if public_url:
        return public_url
    return normalize_text((detail.get("meta_data") or {}).get("canonical_url")) or normalize_text(detail.get("canonical_url"))


def _source_page_url(detail):
    return normalize_text((detail.get("meta_data") or {}).get("canonical_url")) or normalize_text(detail.get("canonical_url"))


def _normalize_job_record(company_slug, detail, company_name):
    req_id = normalize_text(detail.get("req_id") or detail.get("slug"))
    if not req_id:
        raise ValueError(f"GovCIO job is missing req_id/slug for title={detail.get('title')!r}")

    raw_description_source = "\n".join(
        fragment for fragment in (detail.get("description"), detail.get("responsibilities"), detail.get("qualifications")) if fragment
    )
    description_text = _clean_description_text(
        detail.get("description"),
        detail.get("responsibilities"),
        detail.get("qualifications"),
    )

    salary_text, salary_min, salary_max = _extract_salary_fields(raw_description_source)
    travel_text = _extract_travel_text(description_text)
    workplace_type = _normalize_workplace_type(detail.get("tags2") or [])
    canonical_url = _canonical_job_url(detail)
    source_page_url = _source_page_url(detail)
    application_url = normalize_text(detail.get("apply_url"))
    clearance = normalize_text((detail.get("tags1") or [""])[0])
    category_names = _normalize_category_names(detail)

    record = build_base_job_record(
        "govcio",
        company_slug,
        req_id,
        title=detail.get("title", ""),
        location=_build_location(detail),
        url=canonical_url or source_page_url,
        company=company_name or "",
        metadata=_build_metadata(detail),
        updated_at=normalize_text(detail.get("update_date")),
        posted_date=normalize_text(detail.get("posted_date")),
        application_url=application_url,
        source_page_url=source_page_url,
        city=normalize_text(detail.get("city")),
        state=normalize_text(detail.get("state")),
        country=normalize_text(detail.get("country")),
        country_code=normalize_text(detail.get("country_code")),
        postal_code=normalize_text(detail.get("postal_code")),
        location_name=normalize_text(detail.get("location_name")),
        street_address=normalize_text(detail.get("street_address")),
        department=normalize_text(detail.get("department")),
        category=", ".join(category_names),
        clearance=clearance,
        remote_status=normalize_text((detail.get("tags2") or [""])[0]),
        experience_level=normalize_text((detail.get("tags3") or [""])[0]),
        employment_type=_normalize_employment_type(detail.get("employment_type")),
        workplace_type=workplace_type,
        salary_text=salary_text,
        salary_min=salary_min,
        salary_max=salary_max,
        description_text=description_text,
        travel_text=travel_text,
        mentions_travel=bool(travel_text),
        mentions_after_hours="after hours" in description_text.lower(),
        mentions_weekends="weekend" in description_text.lower(),
        mentions_on_call=("on-call" in description_text.lower() or "on call" in description_text.lower()),
        manager_scope=_extract_manager_scope(description_text),
        requisition_id=req_id,
        external_canonical_url=source_page_url,
        api_job_url=DETAIL_API_URL_TEMPLATE.format(
            slug=detail.get("slug"),
            language=detail.get("language", "en-us"),
        ),
    )

    return record


def _extract_listing_jobs(payload):
    jobs = payload.get("jobs") or []
    extracted = []
    for item in jobs:
        data = item.get("data") if isinstance(item, dict) else None
        if isinstance(data, dict) and data.get("slug"):
            extracted.append(data)
    return extracted


def _matches_preferences(job):
    remote_tags = {normalize_text(tag) for tag in (job.get("tags2") or []) if normalize_text(tag)}
    if PREFERRED_REMOTE_TAG not in remote_tags:
        return False

    categories = set(_normalize_category_names(job))
    return bool(categories.intersection(PREFERRED_CATEGORIES))


def _merge_listing_and_detail_payload(listing_job, detail_job):
    merged = dict(listing_job or {})
    merged.update(detail_job or {})

    listing_meta = (listing_job or {}).get("meta_data") or {}
    detail_meta = (detail_job or {}).get("meta_data") or {}
    if listing_meta or detail_meta:
        merged["meta_data"] = dict(listing_meta)
        merged["meta_data"].update(detail_meta)

    return merged


def _fetch_listing_page(session, page, limit):
    response = session.get(
        LIST_API_URL,
        params={
            "page": page,
            "limit": limit,
            "sortBy": "posted_date",
            "tags2": PREFERRED_REMOTE_TAG,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_job_detail(session, slug, language):
    response = session.get(
        DETAIL_API_URL_TEMPLATE.format(slug=slug, language=language),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def collect_govcio_jobs(company_url, company_name=None):
    parsed = urlparse(company_url)
    company_slug = "govcio"
    if parsed.netloc and "govcio" not in parsed.netloc.lower():
        raise ValueError(f"Unsupported GovCIO URL: {company_url}")

    session = build_retry_session()
    limit = DEFAULT_PAGE_SIZE
    seen_slugs = set()
    listing_jobs = []
    total_pages = None
    skipped_preference_count = 0

    for page in range(1, DEFAULT_MAX_PAGES + 1):
        try:
            payload = _fetch_listing_page(session, page=page, limit=limit)
        except requests.RequestException as exc:
            log_collector_event("govcio", f"Failed to fetch GovCIO jobs listing page {page}: {exc}", level="ERROR")
            raise RuntimeError(f"Failed to fetch GovCIO jobs listing page {page}") from exc

        page_jobs = _extract_listing_jobs(payload)
        if not page_jobs:
            log_collector_event("govcio", f"GovCIO listing page {page} returned no jobs; stopping pagination")
            break

        total_count = payload.get("totalCount")
        if total_count and not total_pages:
            total_pages = max(1, ceil(int(total_count) / limit))

        new_jobs = []
        for job in page_jobs:
            slug = normalize_text(job.get("slug"))
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            if not _matches_preferences(job):
                skipped_preference_count += 1
                continue
            new_jobs.append(job)

        if not new_jobs:
            log_collector_event("govcio", f"GovCIO listing page {page} had no new jobs; stopping pagination")
            break

        listing_jobs.extend(new_jobs)
        log_collector_event("govcio", f"Fetched listing page {page} with {len(new_jobs)} new job(s)")

        if total_pages and page >= total_pages:
            break

    normalized_jobs = []
    fallback_to_listing_count = 0

    for index, listing_job in enumerate(listing_jobs, start=1):
        slug = normalize_text(listing_job.get("slug"))
        language = normalize_text(listing_job.get("language")) or "en-us"
        title = normalize_text(listing_job.get("title"))
        log_collector_event("govcio", f"Fetching detail {index}/{len(listing_jobs)}: {title or slug}")

        detail = listing_job
        try:
            detail = _fetch_job_detail(session, slug=slug, language=language)
        except requests.RequestException as exc:
            fallback_to_listing_count += 1
            log_collector_event(
                "govcio",
                f"Detail fetch failed for slug={slug} language={language}; falling back to listing payload: {exc}",
                level="WARN",
            )

        merged_detail = _merge_listing_and_detail_payload(listing_job, detail)
        normalized_jobs.append(_normalize_job_record(company_slug, merged_detail, company_name or "GovCIO"))
        time.sleep(DETAIL_REQUEST_DELAY_SECONDS)

    missing_location_count = sum(1 for job in normalized_jobs if not normalize_text(job.get("location")))
    missing_employment_type_count = sum(1 for job in normalized_jobs if not normalize_text(job.get("employment_type")))
    missing_salary_count = sum(1 for job in normalized_jobs if not normalize_text(job.get("salary_text")))

    log_collector_event(
        "govcio",
        (
            f"Collected {len(normalized_jobs)} preferred jobs from GovCIO"
            + (
                f"; {fallback_to_listing_count} detail request(s) used listing fallback"
                if fallback_to_listing_count
                else ""
            )
            + (
                f"; {skipped_preference_count} remote job(s) skipped outside preferred categories"
                if skipped_preference_count
                else ""
            )
        ),
    )
    log_collector_event(
        "govcio",
        (
            "Diagnostics for GovCIO: "
            f"missing_location={missing_location_count}, "
            f"missing_employment_type={missing_employment_type_count}, "
            f"missing_salary={missing_salary_count}"
        ),
    )

    return normalized_jobs
