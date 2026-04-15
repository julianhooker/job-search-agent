import pandas as pd
from pathlib import Path


def export_jobs_csv(jobs, filename="reports/jobs.csv"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(jobs)
    df.to_csv(path, index=False)

    print(f"Saved {len(jobs)} jobs to {filename}")
