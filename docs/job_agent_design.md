# Job Agent Design

## Overview

This document describes the design of the Job Search Agent: its goals, architecture, data flow, configuration, and extension points. The agent parses job pages, evaluates fit, and produces reports and exports for downstream use.

## Goals

- Automate discovery and structured extraction of job postings.
- Evaluate and rank jobs against user preferences and constraints.
- Produce human-readable and machine-friendly reports for review and tracking.
- Be modular, testable, and extendable to new sources and evaluation strategies.

## High-level Architecture

Components:
- Collectors: fetch or read raw job pages (e.g., `src/collectors/*`).
  - Shared collector utilities in `src/collectors/common.py` provide minimal retrying HTTP fetch helpers, text normalization, and base job record assembly.
  - Lever collection uses the public postings API and maps ATS-specific fields such as `categories`, `workplaceType`, and `salaryRange` into the shared downstream record shape.
- Parsers/Detail Extractors: extract structured fields from HTML (title, company, location, salary, description).
- Evaluators: score and classify jobs against preferences (`src/evaluators/job_evaluator.py`).
- Filters: pre- and post-filters for noise reduction and deduplication (`src/filters`).
- Storage: persist raw and processed records (`src/storage/database.py`, `data/processed`).
- Reporting: export CSV/Markdown/JSON summaries and prompts (`src/reporting`).
- Utilities: config loading, text helpers, shared types (`src/utils`).

## Data Flow

1. Source acquisition: collectors gather raw HTML pages or API responses, using a small shared HTTP helper layer for retry and timeout behavior.
2. Normalization: parsers extract canonical fields and normalize text.
3. Pre-filtering: remove clearly irrelevant postings (e.g., duplicates, missing key fields).
4. Evaluation: run scoring pipelines that compare job attributes to user preferences.
5. Classification: label as Keep/Maybe/Reject and attach rationale/evidence.
6. Persistence & Reporting: save results to storage and generate reports in `reports/`.

## Configuration

- Centralized config files live under `config/` (e.g., `companies.yaml`).
- User preferences (locations, salary range, role keywords, exclusions) are provided via config or runtime args.
- Scoring weights and evaluator thresholds should be configurable to allow tuning without code changes.

## Evaluator Design

- Modular scoring: each evaluator produces a numeric score and short rationale.
- Ensemble: final decision uses weighted combination of evaluator scores.
- Explainability: keep evidence for each decision (matching keywords, missing requirements).
- Extensible: new evaluators implement a simple interface (input: job dict, output: score+rationale).

### Evaluator Output Contract

The manual evaluator workflow writes `reports/evaluator_results.json` as a JSON array of flat evaluator result objects keyed by `job_id`.

Canonical required fields:

- `job_id`: stable link back to the source job, using `source:company_slug:external_job_id`
- `final_recommendation`: `pursue` | `practice` | `pass`
- `fit_score`: integer `1-10`
- `confidence`: `low` | `medium` | `high`
- `ai_durability`: `low` | `medium` | `high`

Common optional fields:

- `key_strengths`: list of strings
- `key_concerns`: list of strings
- `reasoning`: string
- `remote_assessment`: `aligned` | `ambiguous` | `misaligned` | `unknown`
- `travel_assessment`: `low` | `moderate` | `high` | `unknown`
- `salary_assessment`: `meets_target` | `below_target` | `mixed` | `unknown`
- `evaluator_pass`: short label for multi-pass evaluation workflows
- `evaluation_id`: unique identifier for a single evaluation pass
- `evaluated_at`: timestamp string
- `evaluator_model`: model or tool label

Backward compatibility:

- The ingestion layer accepts `recommendation` as an alias for `final_recommendation`.
- If duplicate evaluator entries share the same `job_id`, the report pipeline warns and keeps the last occurrence.
- Unknown optional fields are preserved when merging evaluator results into `reports/evaluator_results_merged.json`.

## Storage and Persistence

- Keep raw HTML (or API response) alongside extracted records for auditability.
- Use CSV/JSON exports for reports and a simple DB abstraction for indexing and lookups (`src/storage/database.py`).
- Base collector records include lightweight collection metadata such as `collected_at` in UTC to help with run tracing and debugging.
- ATS-specific limitations should be documented conservatively; for Lever, some boards may omit or sparsely populate fields like salary, commitment, or workplace type, so normalization should preserve stable identity fields and degrade gracefully.

## Reporting

- Daily human-readable digest in `reports/daily_job_report.md`.
- CSV exports for downstream analysis (`reports/*.csv`).
- JSON exports containing full structured metadata and evaluation traces.

### Manual Evaluation Queue

The pipeline generates `reports/evaluation_queue.json` as a lightweight manual work queue for evaluator review.

- Linkage is by stable `job_id`
- Status values are:
  - `pending`: eligible for manual LLM evaluation and not yet present in evaluator outputs
  - `evaluated`: present in `reports/evaluator_results.json` but not yet merged into the latest final report output
  - `merged`: already present in `reports/evaluator_results_merged.json`
  - `skipped`: not sent for manual evaluation, typically because the job was rejected by the detail filter
- `reports/evaluation_prompts.md` is generated from `pending` jobs only by default
- Setting `FORCE_EVALUATION_PROMPTS=1` causes prompts to be regenerated for all currently eligible jobs
- `python3 -m src.reporting.evaluation_queue` prints summary counts for the queue

### Final Recommendation Scoring

The final report pipeline in `src/reporting/final_report.py` computes a `recommendation_score` for each merged evaluator result before generating `reports/final_recommendations.md` and `reports/evaluator_results_merged.json`.

Current scoring formula:

```text
score =
  (fit_score * 12)
  + confidence_bonus
  + ai_durability_bonus
  + recommendation_bonus
  - concern_keyword_penalty
  + strength_keyword_bonus
  - generic_concern_count_penalty
  + generic_strength_count_bonus

final_score = clamp(score, 0, 100)
```

Base bonuses:

- `confidence`: `high = +8`, `medium = +4`, `low = +0`
- `ai_durability`: `high = +6`, `medium = +3`, `low = +0`
- `final_recommendation`: `pursue = +20`, `practice = +8`, `pass = -8`

Concern keyword penalties are matched case-insensitively across the joined `key_concerns` text:

- `-12` for executive overscope patterns such as `large org leadership`, `executive scope`, `vp scope`, `organization too large`
- `-8` for implementation-heavy product engineering patterns such as `implementation-heavy`, `hands-on product engineering`, `feature delivery`, `coding-heavy`
- `-8` for operational burden patterns such as `on-call`, `operational burden`, `incident response`, `reliability pressure`, `production ownership`
- `-6` for compensation risk patterns such as `salary below target`, `below $135k`, `below 135k`, `compensation risk`
- `-6` for travel or customer-delivery patterns such as `travel`, `customer-facing`, `consulting-heavy`, `sales-adjacent`

Strength keyword bonuses are matched case-insensitively across the joined `key_strengths` text:

- `+8` for architecture/platform/strategy patterns such as `architecture`, `platform`, `systems strategy`, `technical direction`
- `+6` for integration/security-adjacent patterns such as `integration`, `enterprise systems`, `iam`, `authentication`, `authorization`, `security-adjacent`
- `+4` for leadership/communication patterns such as `leadership`, `cross-team alignment`, `explaining technical tradeoffs`

Small generic adjustments are intentionally capped so they do not overpower the semantic signals:

- generic concern count penalty: `min(2 * concern_count, 6)`
- generic strength count bonus: `min(strength_count, 3)`

This scoring design is intended to create more separation between true architecture/platform matches and weaker or more operational/product-engineering fits, while keeping the manual testing workflow unchanged.

## Testing & Validation

- Unit tests for parsers and evaluators using saved sample pages in `data/job_pages/`.
- Integration tests for end-to-end processing of a sample page -> persisted record -> report.
- Evaluate classifier performance periodically using labeled samples and evaluator_results.json.

## Security & Privacy

- Avoid storing unnecessary PII. Mask or omit contact details unless required.
- Secure any credentials used for API collectors; prefer environment variables and not checked-in secrets.

## Extensibility

- Add new collectors for additional ATS platforms by implementing consistent fetch/parse hooks.
- Add new evaluators by following the evaluator interface and registering them in the scoring pipeline.

## Operations

- Run as a scheduled job (cron / CI pipeline) to refresh reports daily.
- Log events and errors to enable quick debugging of parsing or evaluation regressions.

## Future Enhancements

- Interactive UI for reviewing and labeling borderline jobs to improve evaluator training.
- Active learning loop: use reviewer feedback to adapt scoring weights and keyword lists.
- Add similarity/deduplication across postings using embeddings for better filtering.

---

Document created for maintainers and contributors to guide development and extension of the job search agent.
