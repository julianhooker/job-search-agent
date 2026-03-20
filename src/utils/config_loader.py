import yaml


def load_companies(config_path="config/companies.yaml", company_names=None):
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    companies = data["companies"]

    if not company_names:
        return companies

    normalized_names = {str(name).strip().lower() for name in company_names if str(name).strip()}
    return [company for company in companies if str(company.get("name", "")).strip().lower() in normalized_names]
