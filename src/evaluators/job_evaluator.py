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

Return JSON only with this exact schema:
{
  "job_id": "<exact job_id from the job data>",
  "final_recommendation": "pursue" | "practice" | "pass",
  "fit_score": integer from 1 to 10,
  "ai_durability": "low" | "medium" | "high",
  "confidence": "low" | "medium" | "high",
  "key_strengths": ["...", "..."],
  "key_concerns": ["...", "..."],
  "reasoning": "..."
}

Rules:
- The returned "job_id" must exactly match the job_id provided in the job data.
- Return JSON only, with no markdown fences and no extra commentary.
- Do not omit job_id.

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


def build_job_payload(job):
    """
    Keep the payload focused so prompts don't become unnecessarily huge.
    """
    job_id = job.get("job_id")
    if not job_id:
        raise ValueError(
            f"Missing job_id for job title={job.get('title')!r}, company={job.get('company')!r}"
        )

    return {
        "job_id": job_id,
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location", ""),
        "url": job.get("url", ""),
        "prefilter_status": job.get("prefilter_status", ""),
        "prefilter_reasons": job.get("prefilter_reasons", ""),
        "detail_status": job.get("detail_status", ""),
        "detail_reasons": job.get("detail_reasons", ""),
        "salary_text": job.get("salary_text", ""),
        "salary_min": job.get("salary_min", None),
        "salary_max": job.get("salary_max", None),
        "travel_text": job.get("travel_text", ""),
        "employment_type": job.get("employment_type", ""),
        "mentions_travel": job.get("mentions_travel", False),
        "mentions_after_hours": job.get("mentions_after_hours", False),
        "mentions_weekends": job.get("mentions_weekends", False),
        "mentions_on_call": job.get("mentions_on_call", False),
        "manager_scope": job.get("manager_scope", ""),
        "description_text": job.get("description_text", ""),
    }


def build_evaluation_prompt(job):
    payload = build_job_payload(job)

    prompt = f"""
{USER_PROFILE}

{EVALUATION_INSTRUCTIONS}

Job data:
{json.dumps(payload, indent=2, ensure_ascii=False)}
""".strip()

    return prompt