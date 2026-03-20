from src.collectors.greenhouse import collect_greenhouse_jobs
from src.collectors.lever import collect_lever_jobs


COLLECTOR_REGISTRY = {
    "greenhouse": collect_greenhouse_jobs,
    "lever": collect_lever_jobs,
}


def get_collector(platform):
    return COLLECTOR_REGISTRY.get(platform)
