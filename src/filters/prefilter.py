def normalize_text(value):
    return (value or "").strip().lower()


def contains_any(text, patterns):
    return any(pattern in text for pattern in patterns)


REJECT_TITLE_PATTERNS = [
    "account executive",
    "business development",
    "bdr",
    "sdr",
    "sales",
    "recruiter",
    "talent acquisition",
    "marketing",
    "customer success",
    "support engineer",
    "support specialist",
    "legal",
    "attorney",
    "finance",
    "financial analyst",
    "accountant",
    "hr ",
    "human resources",
    "people partner",
    "payroll",
    "billing operations analyst",
    "professional services",
    "forward deploy",
    "engagement manager",
    "customer success engineer",
]

KEEP_TITLE_PATTERNS = [
    "architect",
    "enterprise architect",
    "solutions architect",
    "staff engineer",
    "principal engineer",
    "engineering manager",
    "director of engineering",
    "backend",
    "platform",
    "infrastructure",
    "integration",
    "identity",
    "iam",
    "security engineer",
    "site reliability",
    "sre",
    "database engineer",
    "data engineer",
    "enterprise systems",
    "software engineer",
    "technical architect",
]

MAYBE_TITLE_PATTERNS = [
    "manager",
    "director",
    "analyst",
    "consultant",
    "specialist",
    "operations",
    "technical account",
    "technical program",
    "program manager",
    "product manager",
]


def classify_title(title_text):
    text = normalize_text(title_text)

    if not text:
        return "maybe", ["Missing title"]

    if contains_any(text, REJECT_TITLE_PATTERNS):
        return "reject", ["Title appears outside target role family"]

    if contains_any(text, KEEP_TITLE_PATTERNS):
        return "keep", []

    if contains_any(text, MAYBE_TITLE_PATTERNS):
        return "maybe", ["Title relevance is ambiguous"]

    return "maybe", ["Title does not clearly match target role family"]


def classify_location(location_text):
    text = normalize_text(location_text)

    if not text:
        return "maybe", ["Location missing or unclear"]

    # Hard reject: clearly international / non-US only
    non_us_only_signals = [
        "remote, canada",
        "canada only",
        "emea",
        "apac",
        "europe",
        "united kingdom",
        "uk",
        "ireland",
        "netherlands",
        "germany",
        "france",
        "poland",
        "singapore",
        "india",
        "japan",
        "australia",
        "new zealand",
        "mexico",
        "brazil",
        "united arab emirates",
        "uae",
        "south korea",
        "korea",
    ]

    if contains_any(text, non_us_only_signals):
        return "reject", ["Clearly non-US based"]

    # Strong keep signals
    strong_us_signals = [
        "remote, us",
        "remote, united states",
        "united states",
        "us only",
        "u.s. only",
        "us-based",
        "u.s.-based",
        "lubbock",
    ]

    if contains_any(text, strong_us_signals):
        return "keep", []

    # Ambiguous but plausible
    maybe_us_signals = [
        "north america",
        "americas",
        "america",
        "remote",
    ]

    if contains_any(text, maybe_us_signals):
        return "maybe", ["Location is broad or ambiguous, not clearly US-only"]

    return "maybe", ["Location does not clearly indicate US eligibility"]


def classify_remote_status(location_text):
    text = normalize_text(location_text)

    if "lubbock" in text:
        return "keep", []

    if "remote" in text:
        return "keep", []

    return "reject", ["Not remote and not Lubbock-based"]


def classify_employment_type(job):
    text_parts = [
        normalize_text(job.get("title", "")),
        normalize_text(job.get("metadata", "")),
        normalize_text(job.get("employment_type", "")),
    ]
    combined = " | ".join(text_parts)

    contract_signals = [
        "contract",
        "contractor",
        "temporary",
        "temp ",
        "freelance",
    ]

    if contains_any(combined, contract_signals):
        return "reject", ["Contract or temporary role"]

    return "keep", []


def combine_decisions(decisions):
    """
    decisions = [(status, [reasons]), ...]
    Final status precedence:
      reject > maybe > keep
    """
    final_status = "keep"
    reasons = []

    for status, status_reasons in decisions:
        reasons.extend(status_reasons)

        if status == "reject":
            final_status = "reject"
        elif status == "maybe" and final_status != "reject":
            final_status = "maybe"

    return final_status, reasons


def prefilter_job(job):
    title_status = classify_title(job.get("title", ""))
    location_status = classify_location(job.get("location", ""))
    remote_status = classify_remote_status(job.get("location", ""))
    employment_status = classify_employment_type(job)

    final_status, reasons = combine_decisions([
        title_status,
        location_status,
        remote_status,
        employment_status,
    ])

    return {
        "status": final_status,
        "reasons": reasons,
    }


def prefilter_jobs(jobs):
    kept = []
    maybe = []
    rejected = []

    for job in jobs:
        result = prefilter_job(job)
        job["prefilter_status"] = result["status"]
        job["prefilter_reasons"] = "; ".join(result["reasons"])

        if result["status"] == "keep":
            kept.append(job)
        elif result["status"] == "maybe":
            maybe.append(job)
        else:
            rejected.append(job)

    return kept, maybe, rejected