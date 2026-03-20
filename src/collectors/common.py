from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.id_helpers import build_job_id


DEFAULT_TIMEOUT = 30


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def log_collector_event(source, message, level="INFO"):
    print(f"[collector:{source}] {level}: {message}")


def build_retry_session(
    total_retries=3,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
):
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        read=total_retries,
        connect=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_json(url, timeout=DEFAULT_TIMEOUT, session=None):
    http = session or build_retry_session()
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_text(url, timeout=DEFAULT_TIMEOUT, session=None):
    http = session or build_retry_session()
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def build_base_job_record(
    source,
    company_slug,
    external_job_id,
    *,
    title="",
    location="",
    url="",
    company="",
    **extra,
):
    record = {
        "title": normalize_text(title),
        "location": normalize_text(location),
        "url": normalize_text(url),
        "external_job_id": external_job_id,
        "internal_job_id": external_job_id,
        "company_slug": normalize_text(company_slug),
        "company": normalize_text(company),
        "source": normalize_text(source),
        "job_id": build_job_id(source, company_slug, external_job_id),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    record.update(extra)
    return record
