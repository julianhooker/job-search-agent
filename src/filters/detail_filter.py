import re


def normalize_text(value):
    return (value or "").strip().lower()


def contains_any(text, patterns):
    return any(pattern in text for pattern in patterns)


def role_context_text(job):
    title = normalize_text(job.get("title", ""))
    metadata = normalize_text(job.get("metadata", ""))
    return " | ".join(part for part in (title, metadata) if part)


ADJACENT_RELEVANCE_PATTERNS = [
    "security",
    "identity",
    "iam",
    "platform",
    "integration",
    "infrastructure",
]


REJECT_ROLE_PATTERNS = [
    "people business partner",
    "people operations",
    "human resources",
    "hr ",
    "talent acquisition",
    "recruiter",
    "recruiting",
    "customer success",
    "account executive",
    "sales",
    "business development",
    "growth account executive",
    "regional manager, growth",
    "marketing",
    "finance",
    "legal",
    "compliance partner",
    "people compliance",
]

KEEP_ROLE_PATTERNS = [
    "architect",
    "enterprise architecture",
    "solutions architect",
    "technical architect",
    "backend engineer",
    "staff engineer",
    "principal engineer",
    "engineering manager",
    "platform",
    "infrastructure",
    "security",
    "identity",
    "iam",
    "integration",
    "database engineer",
    "site reliability",
    "sre",
]

CAUTION_ROLE_PATTERNS = [
    "professional services",
    "forward deploy",
    "incident response",
    "soc",
    "security operations",
    "pre-sales",
    "presales",
    "commercial",
    "audit",
    "it audit",
    "sox",
]


def classify_role_fit(job):
    title = normalize_text(job.get("title", ""))
    description = normalize_text(job.get("description_text", ""))
    role_context = role_context_text(job)
    combined = "\n".join(part for part in (role_context, description[:5000]) if part)
    implementation_heavy_title_patterns = [
        "backend engineer",
        "software engineer",
        "frontend engineer",
        "full stack",
        "security engineer",
        "platform engineer",
        "integration engineer",
    ]
    architecture_or_platform_title_patterns = [
        "architecture",
        "architect",
        "platform",
    ]

    # Reject-role patterns are broad and can appear in EEO boilerplate
    # or company descriptions, so only trust them in title/metadata context.
    if contains_any(role_context, REJECT_ROLE_PATTERNS):
        return "reject", ["Role family appears outside target area"]

    if contains_any(combined, KEEP_ROLE_PATTERNS):
        if contains_any(title, implementation_heavy_title_patterns):
            if contains_any(combined, ADJACENT_RELEVANCE_PATTERNS):
                return "maybe", ["Relevant IAM/security/platform area, but title appears engineering-heavy"]
            return "maybe", ["Title appears engineering-heavy relative to target focus"]

        if "engineering manager" in title and not contains_any(title, architecture_or_platform_title_patterns):
            return "maybe", ["Engineering manager title is not clearly architecture/platform-oriented"]

        if contains_any(role_context, CAUTION_ROLE_PATTERNS):
            return "maybe", ["Role appears relevant, but includes cautionary signals"]
        return "keep", []

    return "maybe", ["Role fit is not clearly established from details"]


def classify_salary(job, minimum_salary=135000):
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")

    if salary_min is None and salary_max is None:
        return "keep", ["Compensation not listed"]

    if salary_max is not None and salary_max < minimum_salary:
        return "reject", [f"Salary max below ${minimum_salary:,}"]

    if salary_min is not None and salary_min >= minimum_salary:
        return "keep", []

    return "maybe", [f"Salary range crosses below ${minimum_salary:,}"]


def classify_employment_type(job):
    employment_type = normalize_text(job.get("employment_type", ""))

    if employment_type in {"contract", "temporary"}:
        return "reject", [f"Employment type is {employment_type}"]

    return "keep", []


def classify_workload(job):
    reasons = []
    status = "keep"

    if job.get("mentions_after_hours"):
        reasons.append("Mentions after-hours work")
        status = "maybe"

    if job.get("mentions_weekends"):
        reasons.append("Mentions weekend work")
        status = "maybe"

    if job.get("mentions_on_call"):
        reasons.append("Mentions on-call work")
        status = "maybe"

    title = normalize_text(job.get("title", ""))
    description = normalize_text(job.get("description_text", ""))

    # Only treat incident response as operational burden if the role itself
    # appears to be centered on it, not just mentioning it in passing.
    incident_title_signals = [
        "incident response",
        "sirt",
        "security operations",
        "soc",
    ]

    incident_role_signals = [
        "lead the incident response team",
        "manages and investigates cybersecurity incidents",
        "responsible for threat hunting",
        "alert triage",
        "deep dive dfir",
        "large scale incident response",
    ]

    if contains_any(title, incident_title_signals) or contains_any(description[:2500], incident_role_signals):
        reasons.append("Incident-response work may create operational burden")
        status = "maybe"

    return status, reasons


def classify_travel(job):
    travel_text = normalize_text(job.get("travel_text", ""))
    description = normalize_text(job.get("description_text", ""))

    if not travel_text and "travel" not in description:
        return "keep", []

    combined = f"{travel_text}\n{description}"

    strong_reject_signals = [
        "travel as needed",
        "willingness and ability to travel as needed",
        "up to 25%",
        "up to 50%",
        "25% travel",
        "50% travel",
        "regular travel",
        "significant travel",
    ]

    maybe_signals = [
        "some travel",
        "occasional travel",
        "travel may be required",
        "travel required",
    ]

    if contains_any(combined, strong_reject_signals):
        return "reject", ["Travel requirement appears too open-ended or too high"]

    if contains_any(combined, maybe_signals) or job.get("mentions_travel"):
        return "maybe", ["Travel is mentioned but not clearly within preference"]

    return "keep", []


def classify_manager_scope(job, max_team_size=10):
    scope_text = normalize_text(job.get("manager_scope", ""))

    if not scope_text:
        return "keep", []

    match = re.search(r"(\d+)", scope_text)
    if not match:
        return "maybe", ["Manager scope mentioned but not clearly parseable"]

    count = int(match.group(1))

    if count > max_team_size:
        return "reject", [f"Manager scope appears larger than {max_team_size}"]

    return "keep", []


def combine_decisions(decisions):
    final_status = "keep"
    reasons = []

    for status, status_reasons in decisions:
        reasons.extend(status_reasons)

        if status == "reject":
            final_status = "reject"
        elif status == "maybe" and final_status != "reject":
            final_status = "maybe"

    return final_status, reasons


def detail_filter_job(job):
    decisions = [
        classify_role_fit(job),
        classify_salary(job),
        classify_employment_type(job),
        classify_workload(job),
        classify_travel(job),
        classify_manager_scope(job),
    ]

    final_status, reasons = combine_decisions(decisions)

    return {
        "status": final_status,
        "reasons": reasons,
    }


def detail_filter_jobs(jobs):
    kept = []
    maybe = []
    rejected = []

    for job in jobs:
        result = detail_filter_job(job)
        enriched_job = dict(job)
        enriched_job["detail_status"] = result["status"]
        enriched_job["detail_reasons"] = "; ".join(result["reasons"])

        if result["status"] == "keep":
            kept.append(enriched_job)
        elif result["status"] == "maybe":
            maybe.append(enriched_job)
        else:
            rejected.append(enriched_job)

    return kept, maybe, rejected
