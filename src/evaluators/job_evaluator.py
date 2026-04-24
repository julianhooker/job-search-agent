import json
import re


CANONICAL_EVALUATOR_RESULT_FIELDS = (
    "job_id",
    "final_recommendation",
    "fit_score",
    "ai_durability",
    "confidence",
    "key_strengths",
    "key_concerns",
    "reasoning",
    "remote_assessment",
    "travel_assessment",
    "salary_assessment",
)


CANONICAL_EVALUATOR_RESULT_SCHEMA = """
{
  "job_id": "<exact job_id from the job data>",
  "final_recommendation": "pursue" | "practice" | "pass",
  "fit_score": integer from 1 to 10,
  "ai_durability": "low" | "medium" | "high",
  "confidence": "low" | "medium" | "high",
  "key_strengths": ["...", "..."],
  "key_concerns": ["...", "..."],
  "reasoning": "...",
  "remote_assessment": "aligned" | "ambiguous" | "misaligned" | "unknown",
  "travel_assessment": "low" | "moderate" | "high" | "unknown",
  "salary_assessment": "meets_target" | "below_target" | "mixed" | "unknown"
}
""".strip()


USER_PROFILE = """
Candidate profile:

Experience:
- 25+ years in higher education IT
- Background spans software engineering, enterprise architecture, IAM/security, ERP systems, integrations, and technical leadership
- Experience shaping systems, platforms, and enterprise architecture rather than only implementing individual features
- Comfortable operating across engineering, architecture, and organizational leadership contexts

Preferred role characteristics:
- Remote work required (unless the role is in Lubbock where hybrid could be acceptable)
- Very low travel preferred (generally <10%)
- Minimum salary target roughly $135k
- Does not want contract work
- Open to people management but prefers smaller teams (~8–10 people max)

Strength areas:
- Enterprise architecture
- Integration and enterprise systems
- IAM/security-adjacent systems
- platform or infrastructure architecture
- system design and technical strategy
- translating technical tradeoffs to leadership

Less attractive roles:
- pure feature-factory coding roles
- consulting-heavy delivery roles
- quota or sales roles
- roles that require frequent travel
- operational roles with constant on-call or incident response

AI durability preference:
Roles are preferred when they:
- involve shaping systems and architecture over time
- require explaining technical tradeoffs to leadership
- require judgment across multiple systems
- increase leverage through AI tools rather than being replaced by AI

Roles are less attractive when they are:
- repetitive implementation work
- narrowly scoped feature development
- highly operational / incident-driven
""".strip()


EVALUATION_INSTRUCTIONS = """
Evaluate this job for this candidate.

Return JSON only as a single object using this canonical schema:
{CANONICAL_EVALUATOR_RESULT_SCHEMA}

Rules:
- The returned "job_id" must exactly match the job_id provided in the job data.
- Return JSON only, with no markdown fences and no extra commentary.
- Do not omit job_id.
- Required fields: `job_id`, `final_recommendation`, `fit_score`, `ai_durability`, `confidence`, `remote_assessment`, `travel_assessment`, `salary_assessment`.
- `key_strengths`, `key_concerns`, and `reasoning` should be included whenever possible.
- Always include `remote_assessment`, `travel_assessment`, and `salary_assessment`.
- Use `ambiguous` only for `remote_assessment` when remote/hybrid fit is unclear.
- Use `unknown` for unclear `travel_assessment` or `salary_assessment`.

Interpretation:
- pursue = a real candidate match worth serious consideration
- practice = worth applying to for interview practice or exploratory value, but likely not a true acceptance target
- pass = not a good fit overall

In your reasoning, explicitly consider:
- remote/hybrid fit
- likely travel burden
- salary fit relative to $135k minimum target
- whether the role fits architecture / systems / integration / leadership strengths
- whether management scope seems reasonable
- whether the role looks durable in the face of AI
- whether the role seems likely to create undesirable after-hours / operational burden

Explicitly treat unclear travel expectations as a potential risk if the role appears customer-facing or sales-adjacent.

Do not be overly optimistic. Be specific and grounded in the job text.
""".strip().format(CANONICAL_EVALUATOR_RESULT_SCHEMA=CANONICAL_EVALUATOR_RESULT_SCHEMA)


DECISION_RELEVANT_FIELDS = (
    "job_id",
    "title",
    "company",
    "location",
    "workplace_type",
    "url",
    "prefilter_status",
    "prefilter_reasons",
    "detail_status",
    "detail_reasons",
    "salary_text",
    "salary_min",
    "salary_max",
    "travel_text",
    "mentions_travel",
    "mentions_after_hours",
    "mentions_weekends",
    "mentions_on_call",
    "manager_scope",
    "description_excerpt",
)

DESCRIPTION_EXCERPT_MAX_CHARS = 1200
DESCRIPTION_SKIP_PATTERNS = [
    "who we are",
    "equal opportunity",
    "eeo statement",
    "affirmative action",
    "all qualified applicants",
    "privacy policy",
    "reasonable accommodation",
    "medical, dental",
    "medical dental",
    "paid time off",
    "what does this mean for you",
    "in addition to time off",
    "company overview",
    "about us",
    "background check",
    "drug test",
    "veteran status",
    "disability status",
]
DESCRIPTION_CUT_MARKERS = [
    "who we are:",
    "about us:",
    "benefits:",
    "our benefits",
    "why join",
    "flexible work schedules",
]
DESCRIPTION_PREFER_PATTERNS = [
    "responsibilities",
    "what you'll do",
    "what you will do",
    "requirements",
    "qualifications",
    "about the role",
    "role overview",
    "preferred qualifications",
    "travel",
    "remote",
    "hybrid",
    "architecture",
    "platform",
    "integration",
    "security",
    "identity",
    "iam",
    "manager",
    "leadership",
    "on-call",
]


def _normalize_whitespace(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _description_paragraphs(text):
    normalized = str(text or "").replace("\r", "\n")
    paragraphs = []
    for chunk in re.split(r"\n\s*\n+", normalized):
        paragraph = _normalize_whitespace(chunk)
        if paragraph:
            paragraphs.append(paragraph)
    return paragraphs


def build_description_excerpt(description_text, max_chars=DESCRIPTION_EXCERPT_MAX_CHARS):
    paragraphs = _description_paragraphs(description_text)
    if not paragraphs:
        return ""

    selected = []
    total_chars = 0

    def add_paragraph(paragraph):
        nonlocal total_chars
        if paragraph in selected:
            return
        separator_chars = 2 if selected else 0
        available = max_chars - total_chars - separator_chars
        if available <= 0:
            return
        if len(paragraph) > available:
            trimmed = paragraph[: max(0, available - 3)].rstrip()
            if trimmed:
                selected.append(f"{trimmed}...")
                total_chars = max_chars
            return
        selected.append(paragraph)
        total_chars += len(paragraph) + separator_chars

    preferred = []
    fallback = []
    for paragraph in paragraphs:
        working = paragraph
        lower = working.lower()
        for marker in DESCRIPTION_CUT_MARKERS:
            marker_index = lower.find(marker)
            if marker_index >= 0:
                working = working[:marker_index].rstrip(" -:\n")
                lower = working.lower()
                break
        if not working:
            continue
        if any(pattern in lower for pattern in DESCRIPTION_SKIP_PATTERNS):
            continue
        if len(working) < 40 and not any(pattern in lower for pattern in DESCRIPTION_PREFER_PATTERNS):
            continue
        if any(pattern in lower for pattern in DESCRIPTION_PREFER_PATTERNS):
            preferred.append(working)
        else:
            fallback.append(working)

    for paragraph in preferred + fallback:
        add_paragraph(paragraph)
        if total_chars >= max_chars:
            break

    if not selected:
        return ""

    return "\n\n".join(selected)


def _compact_job_payload(job):
    payload = {}
    for field in DECISION_RELEVANT_FIELDS:
        value = job.get(field)
        if field == "job_id":
            payload[field] = value
            continue
        if value in (None, "", [], {}):
            continue
        if value is False:
            continue
        payload[field] = value
    return payload


def build_job_payload(job):
    """
    Keep the payload focused so prompts don't become unnecessarily huge.
    """
    job_id = job.get("job_id")
    if not job_id:
        raise ValueError(
            f"Missing job_id for job title={job.get('title')!r}, company={job.get('company')!r}"
        )

    compact_job = dict(job)
    compact_job["description_excerpt"] = build_description_excerpt(job.get("description_text", ""))
    payload = _compact_job_payload(compact_job)
    payload["job_id"] = job_id
    return payload


def build_evaluation_prompt_preamble():
    return f"""
COPY THIS SECTION ONCE AT THE START OF A MANUAL EVALUATION SESSION.
IF YOU ARE EVALUATING MULTIPLE JOBS IN ONE CHAT, DO NOT RE-PASTE THIS SECTION FOR EVERY JOB.

{USER_PROFILE}

{EVALUATION_INSTRUCTIONS}
""".strip()


def build_evaluation_prompt(job):
    payload = build_job_payload(job)
    job_id = payload["job_id"]
    title = payload.get("title", "Untitled Job")
    company = payload.get("company", "Unknown Company")

    prompt = f"""
JOB_EVALUATION_BLOCK_START
job_id: {job_id}
company: {company}
title: {title}

Return one JSON object for this job only.

Job data:
{json.dumps(payload, indent=2, ensure_ascii=False)}

JOB_EVALUATION_BLOCK_END
""".strip()

    return prompt
