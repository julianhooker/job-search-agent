from pathlib import Path
import hashlib
import requests
from bs4 import BeautifulSoup
import re


CACHE_DIR = Path("data/job_pages")


def url_to_cache_path(url):
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.html"


def fetch_job_page_html(url, force_refresh=False):
    """
    Fetches job page HTML, using a local cache when available.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = url_to_cache_path(url)

    if cache_path.exists() and not force_refresh:
        return cache_path.read_text(encoding="utf-8")

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    html = response.text
    cache_path.write_text(html, encoding="utf-8")

    return html


def extract_job_detail_fields(html):
    """
    Extract useful fields from a Greenhouse job detail page.
    Trims off application form content and pulls structured hints.
    """
    soup = BeautifulSoup(html, "html.parser")

    main = soup.find("main")
    content_root = main if main else soup

    raw_text = content_root.get_text("\n", strip=True)
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # Cut off the application form and EEO boilerplate
    cutoff_markers = [
        "Apply for this job",
        "First Name",
        "Resume/CV",
        "Cover Letter",
        "Voluntary Self-Identification",
        "Form CC-305",
        "Submit application",
    ]

    trimmed_lines = []
    for line in lines:
        if any(marker.lower() in line.lower() for marker in cutoff_markers):
            break
        trimmed_lines.append(line)

    text = "\n".join(trimmed_lines)
    lowered = text.lower()

    # Salary extraction
    salary_text = ""
    salary_min = None
    salary_max = None

    # First try to find explicit salary range lines
    salary_patterns = [
        r"\$([\d,]+)\s*-\s*\$([\d,]+)",
        r"([\d,]+)\s*-\s*([\d,]+)\s*usd",
    ]

    for pattern in salary_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            salary_min = int(match.group(1).replace(",", ""))
            salary_max = int(match.group(2).replace(",", ""))
            salary_text = match.group(0)
            break

    # Travel extraction
    travel_text = ""
    travel_lines = []

    for line in trimmed_lines:
        if "travel" in line.lower():
            travel_lines.append(line)

    if travel_lines:
        travel_text = " | ".join(travel_lines[:3])

    # Employment type extraction - only from early content
    employment_type = ""
    for line in trimmed_lines[:40]:
        line_lower = line.lower()

        if "federal contractor" in line_lower or "government contractor" in line_lower:
            continue

        if "full-time" in line_lower or "full time" in line_lower:
            employment_type = "Full-time"
            break
        if re.search(r"\bcontract\b", line_lower) or re.search(r"\bcontractor\b", line_lower):
            employment_type = "Contract"
            break
        if "temporary" in line_lower or re.search(r"\btemp\b", line_lower):
            employment_type = "Temporary"
            break

    # Structured flags
    mentions_after_hours = "after hours" in lowered
    mentions_weekends = "weekend" in lowered or "weekends" in lowered
    mentions_on_call = "on-call" in lowered or "on call" in lowered
    mentions_travel = "travel" in lowered

    manager_scope = ""
    manager_match = re.search(r"(\d+\+?\s*(direct reports|engineers|people|team members))", text, re.IGNORECASE)
    if manager_match:
        manager_scope = manager_match.group(1)

    return {
        "description_text": text,
        "salary_text": salary_text,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "travel_text": travel_text,
        "employment_type": employment_type,
        "mentions_travel": mentions_travel,
        "mentions_after_hours": mentions_after_hours,
        "mentions_weekends": mentions_weekends,
        "mentions_on_call": mentions_on_call,
        "manager_scope": manager_scope,
    }


def enrich_job_with_details(job, force_refresh=False):
    """
    Fetch detail page and attach extracted fields to the job dict.
    """
    html = fetch_job_page_html(job["url"], force_refresh=force_refresh)
    details = extract_job_detail_fields(html)

    enriched = dict(job)
    enriched.update(details)

    return enriched


def enrich_jobs_with_details(jobs, force_refresh=False):
    enriched_jobs = []

    for index, job in enumerate(jobs, start=1):
        print(f"Fetching details for {index}/{len(jobs)}: {job.get('title', '')}")
        enriched_jobs.append(enrich_job_with_details(job, force_refresh=force_refresh))

    return enriched_jobs