import pandas as pd
from pathlib import Path


def export_jobs_csv(jobs, filename="reports/jobs.csv"):

    Path("reports").mkdir(exist_ok=True)

    df = pd.DataFrame(jobs)
    df.to_csv(filename, index=False)

    print(f"Saved {len(jobs)} jobs to {filename}")
