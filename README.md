# job-search-agent

## Running One Company

Run only Aledade through the full local pipeline:

```bash
COMPANY_FILTER=Aledade ./.venv/bin/python main.py
```

Smoke test just the configured Aledade Lever collector:

```bash
./.venv/bin/python -m src.collectors.smoke_test --company Aledade
```

## Manual Evaluation Workflow

1. Run the pipeline so the latest review set, queue, and prompts are generated:

```bash
COMPANY_FILTER=Aledade ./.venv/bin/python main.py
```

2. Open `reports/evaluation_prompts.md`.
3. Copy one job block, or a batch of job blocks, into your LLM chat.
4. Copy the LLM's JSON result objects into `reports/evaluator_results.json`.
5. Keep `reports/evaluator_results.json` as a valid JSON array and add new objects without deleting older ones unless that is intentional.
6. Save `reports/evaluator_results.json`.
7. Run the pipeline again so evaluator results are merged into:
   - `reports/evaluator_results_merged.json`
   - `reports/final_recommendations.md`

Queue status meanings in `reports/evaluation_queue.json`:
- `pending`: eligible for manual evaluation and not yet found in `reports/evaluator_results.json`
- `evaluated`: found in `reports/evaluator_results.json` but not yet reflected in the latest merged output
- `merged`: already reflected in `reports/evaluator_results_merged.json`
- `skipped`: not sent to manual evaluation, typically because the detail filter rejected the job

Important:
- If you paste new evaluator output into `reports/evaluator_results.json` but do not save the file before rerunning the pipeline, the new results will not appear in the merged or final reports.

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

Known Lever limitations:
- Some boards omit or sparsely populate `salaryRange`, `commitment`, or `workplaceType`.
- The collector preserves stable identity fields and degrades conservatively when those fields are missing.
- Lever hosted job pages may expose only sparse server-rendered text; the collector therefore preserves Lever API plaintext description fields for downstream filtering when they are richer than the fetched page text.
