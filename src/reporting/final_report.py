import json
from pathlib import Path


RECOMMENDATION_VALUES = {"pursue", "practice", "pass"}
LEVEL_VALUES = {"low", "medium", "high"}
REMOTE_ASSESSMENT_VALUES = {"aligned", "ambiguous", "misaligned", "unknown"}
TRAVEL_ASSESSMENT_VALUES = {"low", "moderate", "high", "unknown"}
SALARY_ASSESSMENT_VALUES = {"meets_target", "below_target", "mixed", "unknown"}


def load_json_file(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def clamp_score(score, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(score)))


def normalize_text_list(values):
    if not isinstance(values, list):
        return []
    return [str(value).strip().lower() for value in values if str(value).strip()]


def concern_keyword_penalty(concerns):
    text = " ".join(normalize_text_list(concerns))
    penalty = 0

    concern_rules = [
        (12, ["large org leadership", "executive scope", "vp scope", "organization too large"]),
        (8, ["implementation-heavy", "hands-on product engineering", "feature delivery", "coding-heavy"]),
        (8, ["on-call", "operational burden", "incident response", "reliability pressure", "production ownership"]),
        (6, ["salary below target", "below $135k", "below 135k", "compensation risk"]),
        (6, ["travel", "customer-facing", "consulting-heavy", "sales-adjacent"]),
    ]

    for amount, keywords in concern_rules:
        if any(keyword in text for keyword in keywords):
            penalty += amount

    return penalty


def strength_keyword_bonus(strengths):
    text = " ".join(normalize_text_list(strengths))
    bonus = 0

    strength_rules = [
        (8, ["architecture", "platform", "systems strategy", "technical direction"]),
        (6, ["integration", "enterprise systems", "iam", "authentication", "authorization", "security-adjacent"]),
        (4, ["leadership", "cross-team alignment", "explaining technical tradeoffs"]),
    ]

    for amount, keywords in strength_rules:
        if any(keyword in text for keyword in keywords):
            bonus += amount

    return bonus


def normalize_string_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_optional_enum(value, allowed_values, default="unknown"):
    normalized = (value or "").strip().lower()
    if not normalized:
        return default
    if normalized not in allowed_values:
        raise ValueError(f"Invalid value {value!r}; expected one of {sorted(allowed_values)}")
    return normalized


def normalize_evaluator_result(raw_result, index):
    if not isinstance(raw_result, dict):
        raise ValueError(f"Evaluator result at index {index} must be an object")

    result = dict(raw_result)

    # Backward-compatible alias support for manual copy/paste workflows.
    if "final_recommendation" not in result and "recommendation" in result:
        result["final_recommendation"] = result.get("recommendation")

    job_id = str(result.get("job_id") or "").strip()
    if not job_id:
        raise ValueError(f"Evaluator result at index {index} is missing required field 'job_id'")

    recommendation = str(result.get("final_recommendation") or "").strip().lower()
    if recommendation not in RECOMMENDATION_VALUES:
        raise ValueError(
            f"Evaluator result for job_id {job_id} has invalid final_recommendation "
            f"{result.get('final_recommendation')!r}"
        )

    try:
        fit_score = int(result.get("fit_score"))
    except Exception:
        raise ValueError(f"Evaluator result for job_id {job_id} is missing or has invalid 'fit_score'")
    if fit_score < 1 or fit_score > 10:
        raise ValueError(f"Evaluator result for job_id {job_id} has fit_score outside 1-10: {fit_score}")

    confidence = normalize_optional_enum(result.get("confidence"), LEVEL_VALUES, default="")
    if not confidence:
        raise ValueError(f"Evaluator result for job_id {job_id} is missing required field 'confidence'")

    ai_durability = normalize_optional_enum(result.get("ai_durability"), LEVEL_VALUES, default="")
    if not ai_durability:
        raise ValueError(f"Evaluator result for job_id {job_id} is missing required field 'ai_durability'")

    normalized = dict(result)
    normalized["job_id"] = job_id
    normalized["final_recommendation"] = recommendation
    normalized["fit_score"] = fit_score
    normalized["confidence"] = confidence
    normalized["ai_durability"] = ai_durability
    normalized["key_strengths"] = normalize_string_list(result.get("key_strengths"))
    normalized["key_concerns"] = normalize_string_list(result.get("key_concerns"))
    normalized["reasoning"] = str(result.get("reasoning") or "").strip()

    # Optional structured assessments to make unknown/ambiguous states explicit.
    if "remote_assessment" in result or "remote_status" in result:
        normalized["remote_assessment"] = normalize_optional_enum(
            result.get("remote_assessment", result.get("remote_status")),
            REMOTE_ASSESSMENT_VALUES,
        )
    if "travel_assessment" in result:
        normalized["travel_assessment"] = normalize_optional_enum(
            result.get("travel_assessment"),
            TRAVEL_ASSESSMENT_VALUES,
        )
    if "salary_assessment" in result:
        normalized["salary_assessment"] = normalize_optional_enum(
            result.get("salary_assessment"),
            SALARY_ASSESSMENT_VALUES,
        )

    # Optional pass metadata for future multi-pass workflows.
    if "evaluator_pass" in result and result.get("evaluator_pass") is not None:
        normalized["evaluator_pass"] = str(result.get("evaluator_pass")).strip()
    if "evaluation_id" in result and result.get("evaluation_id") is not None:
        normalized["evaluation_id"] = str(result.get("evaluation_id")).strip()
    if "evaluated_at" in result and result.get("evaluated_at") is not None:
        normalized["evaluated_at"] = str(result.get("evaluated_at")).strip()
    if "evaluator_model" in result and result.get("evaluator_model") is not None:
        normalized["evaluator_model"] = str(result.get("evaluator_model")).strip()

    return normalized


def normalize_evaluator_results(eval_results):
    if not isinstance(eval_results, list):
        raise ValueError("Evaluator results must be a JSON array of objects")

    normalized_results = []
    seen_job_ids = {}

    for index, raw_result in enumerate(eval_results, start=1):
        normalized = normalize_evaluator_result(raw_result, index)
        job_id = normalized["job_id"]
        if job_id in seen_job_ids:
            print(
                f"Warning: duplicate evaluator result for job_id {job_id}; "
                f"keeping the last occurrence (indices {seen_job_ids[job_id]} and {index})"
            )
        seen_job_ids[job_id] = index
        normalized_results.append(normalized)

    latest_by_job_id = {}
    for normalized in normalized_results:
        latest_by_job_id[normalized["job_id"]] = normalized

    return list(latest_by_job_id.values())


def run_final_report():
    def compute_recommendation_score(item):
        try:
            fit = int(item.get("fit_score") or 0)
        except Exception:
            fit = 0

        score = fit * 12

        conf = (item.get("confidence") or "").lower()
        if conf == "high":
            score += 8
        elif conf == "medium":
            score += 4

        ai = (item.get("ai_durability") or "").lower()
        if ai == "high":
            score += 6
        elif ai == "medium":
            score += 3

        rec = (item.get("final_recommendation") or "").lower()
        if rec == "pursue":
            score += 20
        elif rec == "practice":
            score += 8
        elif rec == "pass":
            score -= 8

        concerns = item.get("key_concerns") or []
        score -= concern_keyword_penalty(concerns)

        strengths = item.get("key_strengths") or []
        score += strength_keyword_bonus(strengths)

        # Keep small generic adjustments, but cap them so text matching dominates.
        generic_concern_penalty = min(2 * len(concerns) if isinstance(concerns, list) else 0, 6)
        generic_strength_bonus = min(len(strengths) if isinstance(strengths, list) else 0, 3)
        score -= generic_concern_penalty
        score += generic_strength_bonus

        return clamp_score(score)

    # Paths
    review_path = Path("reports/jobs_detail_review.json")
    eval_path = Path("reports/evaluator_results.json")
    merged_path = Path("reports/evaluator_results_merged.json")
    md_path = Path("reports/final_recommendations.md")

    print("Loading review jobs from", review_path)
    review_jobs = load_json_file(review_path)
    print(f"Loaded {len(review_jobs)} review jobs")

    print("Loading evaluator results from", eval_path)
    eval_results = load_json_file(eval_path)
    eval_results = normalize_evaluator_results(eval_results)

    print(f"Loaded {len(eval_results)} evaluator results")

    # Index review jobs by job_id
    review_index = {job.get("job_id"): job for job in review_jobs}

    merged = []
    unmatched = []

    for res in eval_results:
        jid = res.get("job_id")
        job = review_index.get(jid)
        if not job:
            unmatched.append(res)
            continue

        merged_item = dict(job)
        # Merge evaluator fields, prefer evaluator fields on collision
        merged_item.update(res)
        # compute and attach recommendation score
        merged_item["recommendation_score"] = compute_recommendation_score(merged_item)
        merged.append(merged_item)

    # Save merged results
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    with merged_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"Merged {len(merged)} results; {len(unmatched)} unmatched evaluator result(s)")

    # Build markdown report with scoring and sorting
    sections = {"pursue": [], "practice": [], "pass": []}

    for item in merged:
        rec = (item.get("final_recommendation") or "").lower()
        key = rec if rec in sections else "pass"
        sections[key].append(item)

    # sort each section by recommendation_score desc, then title asc
    for key in sections:
        sections[key].sort(key=lambda j: (-(j.get("recommendation_score") or 0), (j.get("title") or "").lower()))

    # compute top scores
    top_scores = {}
    for key in sections:
        if sections[key]:
            top_scores[key] = max((j.get("recommendation_score") or 0) for j in sections[key])
        else:
            top_scores[key] = None

    lines = ["# Final Recommendations", ""]

    # Summary counts with top score
    total = len(merged)
    counts = {k: len(v) for k, v in sections.items()}
    def top_text(k):
        return str(top_scores[k]) if top_scores[k] is not None else "N/A"

    lines.append(f"Total evaluated jobs: {total}")
    lines.append("")
    lines.append(f"- Pursue: {counts.get('pursue', 0)} (top score: {top_text('pursue')})")
    lines.append(f"- Practice: {counts.get('practice', 0)} (top score: {top_text('practice')})")
    lines.append(f"- Pass: {counts.get('pass', 0)} (top score: {top_text('pass')})")
    lines.append("- Scoring model: weighted fit + confidence + AI durability + keyword bonuses/penalties")
    lines.append("")

    # Debug line for top pursue score
    if top_scores.get("pursue") is not None:
        print(f"Top pursue score: {top_scores['pursue']}")

    score_values = [item.get("recommendation_score", 0) for item in merged]
    if score_values:
        print(f"Score range across merged jobs: {min(score_values)} to {max(score_values)}")

        top_jobs = sorted(
            merged,
            key=lambda j: (-(j.get("recommendation_score") or 0), (j.get("title") or "").lower()),
        )[:3]
        print("Top 3 jobs by score:")
        for job in top_jobs:
            print(
                f"- {(job.get('title') or 'Untitled')} "
                f"[{(job.get('final_recommendation') or 'pass').lower()}]: "
                f"{job.get('recommendation_score', 0)}"
            )

    for section in ["pursue", "practice", "pass"]:
        lines.append(f"## {section.title()} ({len(sections[section])})")
        lines.append("")

        for item in sections[section]:
            jid = item.get("job_id", "unknown-job-id")
            title = item.get("title", "Untitled")
            company = item.get("company", "Unknown")
            url = item.get("url", "")
            fit = item.get("fit_score", "")
            recommendation = (item.get("final_recommendation") or "").lower()
            confidence = item.get("confidence", "")
            ai = item.get("ai_durability", "")
            strengths = item.get("key_strengths") or []
            concerns = item.get("key_concerns") or []
            reasoning = item.get("reasoning") or ""
            score = item.get("recommendation_score", "")

            if not item.get("title"):
                print(f"Warning: merged item missing title for job_id {jid}")
            if not item.get("url"):
                print(f"Warning: merged item missing url for job_id {jid}")

            lines.append(f"### {title} — {company}")
            lines.append("")
            lines.append(f"- Score: {score}")
            lines.append(f"- URL: {url}")
            lines.append(f"- Fit score: {fit}")
            lines.append(f"- Recommendation: {recommendation}")
            lines.append(f"- Confidence: {confidence}")
            lines.append(f"- AI durability: {ai}")
            lines.append("")
            if strengths:
                lines.append("**Key strengths**:")
                for s in strengths:
                    lines.append(f"- {s}")
                lines.append("")

            if concerns:
                lines.append("**Key concerns**:")
                for c in concerns:
                    lines.append(f"- {c}")
                lines.append("")

            if reasoning:
                lines.append("**Reasoning**:")
                lines.append("")
                lines.append(reasoning)
                lines.append("")

        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote markdown report to {md_path} and merged JSON to {merged_path}")

    # Debug summary prints
    print(f"Number of review jobs: {len(review_jobs)}")
    print(f"Number of evaluator results: {len(eval_results)}")
    print(f"Number of merged results: {len(merged)}")
    print(f"Number of unmatched evaluator results: {len(unmatched)}")

    return {
        "review_jobs": len(review_jobs),
        "eval_results": len(eval_results),
        "merged": len(merged),
        "unmatched": len(unmatched),
    }
