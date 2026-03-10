def normalize_text(value):
    return (value or "").strip().lower()


def looks_us_based(location_text):
    text = normalize_text(location_text)

    if not text:
        return False

    us_signals = [
        "united states",
        "usa",
        "us ",
        "u.s.",
        "u.s.a.",
        "us-only",
        "us only",
        "u.s. only",
        "america",
    ]

    non_us_signals = [
        "canada",
        "emea",
        "apac",
        "europe",
        "united kingdom",
        "uk",
        "germany",
        "france",
        "india",
        "singapore",
        "australia",
        "new zealand",
        "japan",
        "netherlands",
        "ireland",
        "poland",
        "mexico",
        "brazil",
    ]

    if any(signal in text for signal in non_us_signals):
        return False

    if any(signal in text for signal in us_signals):
        return True

    return False


def looks_remote(location_text):
    text = normalize_text(location_text)
    return "remote" in text


def is_lubbock(location_text):
    text = normalize_text(location_text)
    return "lubbock" in text


def prefilter_job(job):
    """
    Returns:
      {
        "keep": bool,
        "reasons": [list of strings]
      }
    """

    reasons = []
    location = job.get("location", "")

    remote = looks_remote(location)
    lubbock = is_lubbock(location)
    us_based = looks_us_based(location)

    if not us_based:
        reasons.append("Not clearly US-based")

    if not remote and not lubbock:
        reasons.append("Not remote and not Lubbock-based")

    keep = len(reasons) == 0

    return {
        "keep": keep,
        "reasons": reasons
    }


def prefilter_jobs(jobs):
    kept = []
    rejected = []

    for job in jobs:
        result = prefilter_job(job)
        job["prefilter_keep"] = result["keep"]
        job["prefilter_reasons"] = "; ".join(result["reasons"])

        if result["keep"]:
            kept.append(job)
        else:
            rejected.append(job)

    return kept, rejected