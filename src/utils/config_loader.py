import yaml


def load_companies(config_path="config/companies.yaml"):
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    return data["companies"]
