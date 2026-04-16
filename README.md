# job-search-agent

## Reports Layout

User-facing files stay at the `reports/` root:

- `reports/final_recommendations.md`: final human-readable recommendations
- `reports/daily_job_report.md`: daily summary report
- `reports/evaluation_prompts.md`: single-job manual evaluation prompts
- `reports/evaluation_batch_prompt.md`: combined batch prompt for all currently pending jobs
- `reports/evaluation_batch_prompt_aledade.md`: per-company Aledade batch prompt
- `reports/evaluation_batch_prompt_gitlab.md`: per-company GitLab batch prompt
- `reports/evaluation_batch_prompt_govcio.md`: per-company GovCIO batch prompt
- `reports/evaluator_results.json`: manual evaluator input file

Generated state and intermediate pipeline files live under subfolders:

- `reports/data/jobs_detail_review.json`: current reviewable jobs after enrichment/filtering
- `reports/state/evaluation_queue.json`: evaluation queue state
- `reports/state/evaluator_results_merged.json`: generated merged evaluator output

## Running One Company

Run only Aledade through the full local pipeline:

```bash
COMPANY_FILTER=Aledade ./.venv/bin/python main.py
```

Smoke test just the configured Aledade Lever collector:

```bash
./.venv/bin/python -m src.collectors.smoke_test --company Aledade
```

Run only GovCIO through the full local pipeline:

```bash
COMPANY_FILTER=GovCIO ./.venv/bin/python main.py
```

Smoke test just the configured GovCIO collector:

```bash
./.venv/bin/python -m src.collectors.smoke_test --company GovCIO
```

## Manual Evaluation Workflow

1. Run the pipeline so the latest review set, queue, and prompts are generated:

```bash
COMPANY_FILTER=Aledade ./.venv/bin/python main.py
```

2. Choose one of the generated prompt files:
   - `reports/evaluation_prompts.md` for one-job-at-a-time evaluation
   - `reports/evaluation_batch_prompt_*.md` for per-company batch evaluation
   - `reports/evaluation_batch_prompt.md` for the combined all-companies batch
3. Paste the selected prompt into your LLM chat and collect the JSON results.
4. Copy the LLM's JSON result objects into `reports/evaluator_results.json`.
5. Keep `reports/evaluator_results.json` as a valid JSON array and add new objects without deleting older ones unless that is intentional.
6. Save `reports/evaluator_results.json`.
7. Run the pipeline again so evaluator results are merged into:
   - `reports/state/evaluator_results_merged.json`
   - `reports/final_recommendations.md`

Queue status meanings in `reports/state/evaluation_queue.json`:
- `pending`: eligible for manual evaluation and not yet found in `reports/evaluator_results.json`
- `evaluated`: found in `reports/evaluator_results.json` but not yet reflected in the latest merged output
- `merged`: already reflected in `reports/state/evaluator_results_merged.json`
- `skipped`: not sent to manual evaluation, typically because the detail filter rejected the job

Important:
- If you paste new evaluator output into `reports/evaluator_results.json` but do not save the file before rerunning the pipeline, the new results will not appear in the merged or final reports.
- `reports/evaluator_results.json` is the manual input file. `reports/state/evaluator_results_merged.json` is generated output and should not be edited by hand.
- The combined batch prompt can be too large for a temporary ChatGPT chat. Prefer the per-company files when possible.

## Adding a Lever Company

Add an entry to `config/companies.yaml` like:

```yaml
- name: Aledade
  platform: lever
  url: https://jobs.lever.co/aledade
```

Supported Lever URL forms:
- `https://jobs.lever.co/<company_slug>`
- `https://jobs.eu.lever.co/<company_slug>`
- `https://api.lever.co/v0/postings/<company_slug>?mode=json`

## Adding GovCIO

GovCIO is configured as:

```yaml
- name: GovCIO
  platform: govcio
  url: https://govcio.com/jobs/
```

Implementation notes:
- The GovCIO collector uses GovCIO's public careers search API at `careers.govcio.com` for pagination and per-job detail payloads.
- The collector preserves the careers page URL as the canonical `url` because it is the stable machine-discoverable source page exposed by the public API.
- `application_url` is captured separately from the iCIMS apply link when present.
- The collector currently prefers only `Fully remote` GovCIO roles and keeps only these Areas of Interest: `Information Technology`, `Software Engineering Services`, and `Other`.
- GovCIO jobs can be batch-evaluated using `reports/evaluation_batch_prompt_govcio.md`.

Known Lever limitations:
- Some boards omit or sparsely populate `salaryRange`, `commitment`, or `workplaceType`.
- The collector preserves stable identity fields and degrades conservatively when those fields are missing.
- Lever hosted job pages may expose only sparse server-rendered text; the collector therefore preserves Lever API plaintext description fields for downstream filtering when they are richer than the fetched page text.
