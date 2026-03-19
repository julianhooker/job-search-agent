# AI Context

## Project Overview

- This is a local AI-assisted job search pipeline written in Python.
- It collects jobs, filters them, prepares manual evaluation prompts, ingests evaluator output, and produces a ranked report.
- The current workflow combines automated pipeline steps with a manual LLM evaluation step.

## Pipeline Architecture

- `config/companies.yaml`
  - Defines target companies and collector configuration
- Collectors
  - Greenhouse is currently implemented
  - Shared collector utilities now live in `src/collectors/common.py`
  - Shared utilities are intentionally minimal: retrying HTTP fetch helpers, text normalization, and base job record assembly
- Prefilter
  - Uses title, location, remote, and contract signals
- Detail enrichment
  - Scrapes full job description and metadata
- Detail filter
  - Uses role fit, salary, travel, workload, and manager scope signals
- Manual evaluation queue generation
  - `reports/evaluation_queue.json` tracks `pending`, `evaluated`, `merged`, and `skipped`
- Evaluation prompt generation
  - `reports/evaluation_prompts.md` is generated for pending jobs only by default
- Manual evaluator step
  - LLM outputs are copied into `reports/evaluator_results.json`
- Evaluator result ingestion
  - Merges evaluator output back to job metadata by `job_id`
- Scoring and ranking
  - Produces a recommendation score within each recommendation bucket
- Final outputs
  - `reports/evaluator_results_merged.json`
  - `reports/final_recommendations.md`
  - `reports/daily_job_report.md`

## Data Contracts

- `job_id`
  - Format: `source:company_slug:external_job_id`
  - This is the stable join key across collected jobs, prompts, evaluator results, queue entries, and merged reports
- Collected job metadata
  - Base collector records now include `collected_at` as a lightweight UTC timestamp for run/debug context
  - Core identity fields remain `job_id`, `source`, `company_slug`, and `external_job_id`
- `reports/evaluator_results.json`
  - List of evaluator result objects
  - Canonical required fields:
    - `job_id`
    - `final_recommendation`
    - `fit_score`
    - `confidence`
    - `ai_durability`
  - Common optional fields:
    - `key_strengths`
    - `key_concerns`
    - `reasoning`
    - `remote_assessment`
    - `travel_assessment`
    - `salary_assessment`
    - `evaluator_pass`
    - `evaluation_id`
    - `evaluated_at`
    - `evaluator_model`
  - Backward-compatible alias accepted during ingestion:
    - `recommendation` -> `final_recommendation`
  - If duplicate `job_id` entries appear, the pipeline warns and keeps the last one
- `reports/evaluation_queue.json`
  - Generated manual work queue keyed by `job_id`
  - Status values: `pending`, `evaluated`, `merged`, `skipped`
  - Used to avoid re-presenting already evaluated jobs in `reports/evaluation_prompts.md` unless forced
  - `pending` means eligible for manual evaluation and not yet present in evaluator output
  - `evaluated` means present in `reports/evaluator_results.json` but not yet reflected in the latest merged output
  - `merged` means already present in `reports/evaluator_results_merged.json`
  - `skipped` means not sent to manual evaluation, typically because the job was rejected by the detail filter
- `reports/evaluator_results_merged.json`
  - Contains merged job data, evaluator output, and computed recommendation score
  - Each merged object should contain both job metadata and evaluator metadata
  - Key fields include `job_id`, `title`, `company`, `url`, `location` if available, evaluator fields, and `recommendation_score`

## Candidate Constraints

- Remote required unless local to Lubbock, TX
- Low travel preferred
- No contract work
- Salary target is roughly `$135k+`
- Prefers architecture, platform, integration, and IAM/security-adjacent roles
- Avoids implementation-heavy product engineering roles
- Prefers small-team leadership, roughly `8-10` people
- Does not want large-org leadership or executive-scope roles

## Recommendation Meanings

- `pursue`
  - A real target role worth serious consideration
- `practice`
  - Worth applying to for interview practice or exploratory value, but likely not a top acceptance target
- `pass`
  - Not a good fit overall relative to the candidate's goals and constraints

## Scoring Model (Current)

- Base score starts from `fit_score * weight`
- Adds bonuses for confidence and AI durability
- Adds bonuses for architecture, integration, and security alignment via keyword matching
- Applies penalties for:
  - Large-org leadership or executive scope
  - Implementation-heavy roles
  - Operational burden or on-call pressure
  - Salary below target
  - Travel-heavy or customer-facing roles
- Scores are clamped to a fixed range, currently `0-100`
- Scores are used to rank jobs within `pursue`, `practice`, and `pass` sections

## Current Status

- `job_id` implemented and stable
- Small shared collector layer implemented for retrying HTTP fetches and base record normalization
- Collector to filter to evaluator pipeline working
- Evaluation queue generation working
- Evaluator prompt generation working
- Manual evaluation workflow in place
- Evaluator results ingestion working
- Scoring and ranking implemented
- `final_recommendations.md` generated successfully

## Key Files

- `main.py`
  - Primary orchestration entry point for the local pipeline
- `src/evaluators/job_evaluator.py`
  - Defines the evaluator prompt and the canonical evaluator output contract
- `src/collectors/common.py`
  - Tiny shared collector helpers for retrying HTTP fetches, normalization, and base job record creation
- `src/reporting/evaluation_queue.py`
  - Builds the manual work queue and prints queue summary counts
- `src/reporting/final_report.py`
  - Normalizes evaluator results, merges them with job metadata, computes scores, and writes final reports
- `reports/evaluation_queue.json`
  - Manual evaluation work queue
- `reports/evaluation_prompts.md`
  - Prompt batch for pending jobs
- `reports/evaluator_results.json`
  - Manually pasted evaluator outputs
- `reports/evaluator_results_merged.json`
  - Merged evaluator plus job metadata with scores
- `reports/final_recommendations.md`
  - Human-readable ranked report

## Development Workflow

- Use ChatGPT for system design and reasoning
- Use Codex for modifying code in the repo
- Manual evaluation step is currently used instead of live LLM API calls
- Run the pipeline to refresh `reports/evaluation_queue.json`
- Review `reports/evaluation_prompts.md` for `pending` jobs only
- Set `FORCE_EVALUATION_PROMPTS=1` to regenerate prompts for all currently eligible jobs
- Use `python3 -m src.reporting.evaluation_queue` to print queue summary counts
- Use `python3 -m src.reporting.evaluation_queue --generate` to rebuild the queue from existing report JSON files without running the full collection pipeline

## Next Planned Improvements

- Automate the LLM evaluation step
- Support multiple job board collectors
- Improve the scoring model further
- Add daily automated run/report
- Possibly add notifications such as email or Slack

## Guidance For Future AI Assistants

- Treat `job_id` as the canonical identity key across the entire pipeline
- Preserve backward compatibility for `reports/evaluator_results.json` whenever possible, because it is maintained manually
- Do not automate LLM calls unless explicitly asked; the current evaluator workflow is intentionally manual
- Keep changes small and local to the relevant pipeline stage unless there is a clear need to refactor
- Prefer the shared collector helpers in `src/collectors/common.py` for future ATS collectors rather than adding new ad hoc `requests.get(...)` patterns
- When changing evaluator output handling, prefer normalization and validation over breaking schema changes
- When changing prompt generation, queue logic, or merge logic, verify that `reports/evaluation_prompts.md`, `reports/evaluation_queue.json`, and `reports/evaluator_results_merged.json` still align by `job_id`
