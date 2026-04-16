from src.collectors.govcio import collect_govcio_jobs
from src.collectors.greenhouse import collect_greenhouse_jobs
from src.collectors.lever import collect_lever_jobs


COLLECTOR_REGISTRY = {
    "govcio": collect_govcio_jobs,
    "greenhouse": collect_greenhouse_jobs,
    "lever": collect_lever_jobs,
}


def get_collector(platform):
    return COLLECTOR_REGISTRY.get(platform)
