import json


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

Rules:
- The returned "job_id" must exactly match the job_id provided in the job data.
- Return JSON only, with no markdown fences and no extra commentary.
- Do not omit job_id.
- Required fields: `job_id`, `final_recommendation`, `fit_score`, `ai_durability`, `confidence`.
- `key_strengths`, `key_concerns`, and `reasoning` should be included whenever possible.
- Include `remote_assessment`, `travel_assessment`, and `salary_assessment` when the job text makes those judgments possible.
- Use `unknown` or `ambiguous` rather than guessing when salary, travel, or remote status is unclear.

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
""".strip()


DECISION_RELEVANT_FIELDS = (
    "job_id",
    "title",
    "company",
    "location",
    "url",
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
    "description_text",
)


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

    payload = _compact_job_payload(job)
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
