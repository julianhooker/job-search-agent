# AI Context

## Project Overview

- This is a local AI-assisted job search pipeline written in Python.
- It collects jobs, filters them, evaluates them, and produces a ranked report.
- The current workflow combines automated pipeline steps with a manual LLM evaluation step.

## Pipeline Architecture

- `config/companies.yaml`
- Collectors
  - Greenhouse is currently implemented
- Prefilter
  - Title, location, remote, and contract signals
- Detail enrichment
  - Scrapes full job description and metadata
- Detail filter
  - Role fit, salary, travel, workload, and manager scope
- `reports/evaluation_prompts.md` generation
- Manual evaluation step
  - LLM outputs are copied into `reports/evaluator_results.json`
- Evaluator results ingestion
  - Merges evaluator output by `job_id`
- Scoring and ranking
- `reports/final_recommendations.md` output

## Data Contracts

- `job_id`
  - Format: `source:company_slug:external_job_id`
- `reports/evaluator_results.json`
  - List of evaluation result objects
  - Each object includes `job_id`, recommendation, `fit_score`, confidence, AI durability, strengths, concerns, and reasoning
- `reports/evaluator_results_merged.json`
  - Contains merged job data, evaluator output, and computed recommendation score

## Candidate Constraints

- Remote required unless local to Lubbock, TX
- Low travel preferred
- No contract work
- Salary target is roughly `$135k+`
- Prefers architecture, platform, integration, and IAM/security-adjacent roles
- Avoids implementation-heavy product engineering roles
- Prefers small-team leadership, roughly `8-10` people
- Does not want large-org leadership or executive-scope roles

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
- Evaluator prompt generation working
- Manual evaluation workflow in place
- Evaluator results ingestion working
- Scoring and ranking implemented
- `final_recommendations.md` generated successfully

## Development Workflow

- Use ChatGPT for system design and reasoning
- Use Codex for modifying code in the repo
- Manual evaluation step is currently used instead of live LLM API calls

## Next Planned Improvements

- Automate the LLM evaluation step
- Support multiple job board collectors
- Improve the scoring model further
- Add daily automated run/report
- Possibly add notifications such as email or Slack
