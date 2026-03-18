import json
from pathlib import Path


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

    # Validate evaluator results is an array
    if not isinstance(eval_results, list):
        raise ValueError("Evaluator results must be a JSON array of objects")

    # Validate each evaluator result has a job_id
    missing = [r for r in eval_results if not isinstance(r, dict) or not r.get("job_id")]
    if missing:
        raise ValueError(f"Found {len(missing)} evaluator result(s) missing 'job_id'")

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
