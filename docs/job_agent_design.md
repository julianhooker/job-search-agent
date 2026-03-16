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
- Parsers/Detail Extractors: extract structured fields from HTML (title, company, location, salary, description).
- Evaluators: score and classify jobs against preferences (`src/evaluators/job_evaluator.py`).
- Filters: pre- and post-filters for noise reduction and deduplication (`src/filters`).
- Storage: persist raw and processed records (`src/storage/database.py`, `data/processed`).
- Reporting: export CSV/Markdown/JSON summaries and prompts (`src/reporting`).
- Utilities: config loading, text helpers, shared types (`src/utils`).

## Data Flow

1. Source acquisition: collectors gather raw HTML pages or API responses.
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

## Storage and Persistence

- Keep raw HTML (or API response) alongside extracted records for auditability.
- Use CSV/JSON exports for reports and a simple DB abstraction for indexing and lookups (`src/storage/database.py`).

## Reporting

- Daily human-readable digest in `reports/daily_job_report.md`.
- CSV exports for downstream analysis (`reports/*.csv`).
- JSON exports containing full structured metadata and evaluation traces.

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
