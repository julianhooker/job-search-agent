# AI Context

## Project Overview

- This is a local AI-assisted job search pipeline written in Python.
- It collects jobs, filters them, prepares manual evaluation prompts, ingests evaluator output, and produces a ranked report.
- The current workflow combines automated pipeline steps with a manual LLM evaluation step.

## Pipeline Architecture

- `config/companies.yaml`
  - Defines target companies and collector configuration
  - Example Lever-backed company entry now includes Aledade via `https://jobs.lever.co/aledade`
- Collectors
  - Greenhouse is currently implemented
  - Lever is also supported via the public postings API
  - Shared collector utilities now live in `src/collectors/common.py`
  - Shared utilities are intentionally minimal: retrying HTTP fetch helpers, text normalization, and base job record assembly
- Prefilter
  - Uses title, location, remote, and contract signals
  - `reject` at this stage is final for manual workflow purposes and does not continue to detail enrichment
- Detail enrichment
  - Scrapes full job description and metadata
- Detail filter
  - Uses role fit, salary, travel, workload, and manager scope signals
  - Only `keep`, `maybe`, and backward-compatible `review` statuses remain eligible for manual evaluation
- Manual evaluation queue generation
  - `reports/state/evaluation_queue.json` tracks `pending`, `evaluated`, `merged`, and `skipped`
  - `skipped` covers confident auto-rejects from either prefilter or detail filter so they stay auditable without creating manual work
- Evaluation prompt generation
  - `reports/evaluation_prompts.md` is generated as an index for pending jobs only by default
  - Individual self-contained prompt files are written to `reports/evaluation_prompts/batch_###.md`
  - Prompt batching is deterministic and constrained by max jobs per batch plus an approximate character budget
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
  - Only jobs with pipeline status `keep`, `maybe`, or legacy `review` are eligible for manual evaluation
  - `pending` means eligible for manual evaluation and not yet present in evaluator output
  - `evaluated` means present in `reports/evaluator_results.json` but not yet reflected in the latest merged output
  - `merged` means already present in `reports/evaluator_results_merged.json`
  - `skipped` means not sent to manual evaluation because it was confidently auto-rejected upstream
- `reports/evaluator_results_merged.json`
  - Contains merged job data, evaluator output, and computed recommendation score
  - Each merged object should contain both job metadata and evaluator metadata
  - Key fields include `job_id`, `title`, `company`, `url`, `location` if available, evaluator fields, and `recommendation_score`
- Prompt batch files
  - `reports/evaluation_prompts.md` is an index listing generated batches
  - `reports/evaluation_prompts/batch_###.md` files are self-contained prompt payloads for manual evaluation
  - Default prompt batching lives in `config/settings.yaml`
  - Current defaults are `4` jobs per batch and roughly `12000` chars per batch
  - Environment overrides:
    - `EVALUATION_PROMPT_BATCH_SIZE`
    - `EVALUATION_PROMPT_MAX_CHARS`

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
- `src/collectors/lever.py`
  - Public Lever postings collector that normalizes Lever API fields into the shared downstream job shape
- `src/reporting/evaluation_queue.py`
  - Builds the manual work queue and prints queue summary counts
- `src/reporting/final_report.py`
  - Normalizes evaluator results, merges them with job metadata, computes scores, and writes final reports
- `reports/evaluation_queue.json`
  - Manual evaluation work queue
- `reports/evaluation_prompts.md`
  - Prompt batch index for pending jobs
- `reports/evaluation_prompts/`
  - Self-contained prompt batch files such as `batch_001.md`
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
- Keep the manual evaluator reserved for judgment calls; obvious auto-rejects should remain visible in reports but never re-enter prompt generation
- Run the pipeline to refresh `reports/state/evaluation_queue.json`
- Set `COMPANY_FILTER=Aledade` to run only Aledade through the existing pipeline
- Review `reports/evaluation_prompts.md` for the list of `pending` job batches only
- Open one file from `reports/evaluation_prompts/` and paste that single batch into the evaluator chat
- Set `FORCE_EVALUATION_PROMPTS=1` to regenerate prompts for all currently eligible jobs
- Edit `config/settings.yaml` to change the default max jobs per prompt batch or approximate prompt size budget
- Set `EVALUATION_PROMPT_BATCH_SIZE` or `EVALUATION_PROMPT_MAX_CHARS` only when you want a one-off override
- Use `python3 -m src.reporting.evaluation_queue` to print queue summary counts
- Use `python3 -m src.reporting.evaluation_queue --generate` to rebuild the queue from existing report files without running the full collection pipeline
- Use `./.venv/bin/python -m src.collectors.smoke_test --company Aledade` to validate only the configured Aledade Lever collector and print sample normalized records

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
- Lever collection currently depends on the public postings API fields such as `categories`, `workplaceType`, and `salaryRange`; if a company’s Lever board omits those fields, normalization falls back conservatively and malformed records are skipped with warnings
- Lever hosted pages may be sparsely server-rendered, so the collector preserves the richer Lever API plaintext description when detail-page extraction returns only thin header text
- To add a Lever company, add a `platform: lever` entry in `config/companies.yaml` using a public board URL such as `https://jobs.lever.co/<company_slug>`; Aledade is the first real configured example
- When changing evaluator output handling, prefer normalization and validation over breaking schema changes
- When changing prompt generation, queue logic, or merge logic, verify that `reports/evaluation_prompts.md`, `reports/evaluation_queue.json`, and `reports/evaluator_results_merged.json` still align by `job_id`
