import json
from pathlib import Path
from typing import Any, Union


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CAMPAIGNS_PATH = DATA_DIR / "campaigns.json"
COPY_TEMPLATES_PATH = DATA_DIR / "templates.json"
INDUSTRY_TEMPLATES_PATH = DATA_DIR / "industry_templates.json"


class JsonStore:
    """Internal JSON repository. UI modules use the domain functions below."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return payload if isinstance(payload, list) else []

    def save_all(self, records: list[dict[str, Any]]) -> None:
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_path.replace(self.path)

    def add(self, record: dict[str, Any]) -> None:
        records = self.load()
        records.append(record)
        self.save_all(records)

    def update(self, record_id: str, values: dict[str, Any]) -> bool:
        records = self.load()
        for index, record in enumerate(records):
            if record.get("id") == record_id:
                records[index] = {**record, **values, "id": record_id}
                self.save_all(records)
                return True
        return False

    def delete(self, record_id: str) -> bool:
        records = self.load()
        remaining = [item for item in records if item.get("id") != record_id]
        if len(remaining) == len(records):
            return False
        self.save_all(remaining)
        return True


def _campaign_store(path: Union[str, Path] = CAMPAIGNS_PATH) -> JsonStore:
    return JsonStore(path)


def _normalize_campaign(campaign: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(campaign)
    defaults = {
        "event_time": "",
        "location": "",
        "address": "",
        "primary_industry": normalized.get("suitable_industries", ""),
        "summary": "",
        "introduction": normalized.get("highlights", ""),
        "activity_point_1": "",
        "activity_point_2": "",
        "activity_point_3": "",
        "activity_point_4": "",
        "email_title_a": "",
        "email_title_b": "",
        "email_title_c": "",
    }
    for key, value in defaults.items():
        normalized.setdefault(key, value)
    return normalized


def load_campaigns(path: Union[str, Path] = CAMPAIGNS_PATH) -> list[dict[str, Any]]:
    return [_normalize_campaign(item) for item in _campaign_store(path).load()]


def save_campaign(
    campaign: dict[str, Any], path: Union[str, Path] = CAMPAIGNS_PATH
) -> None:
    _campaign_store(path).add(_normalize_campaign(campaign))


def update_campaign(
    campaign_id: str,
    values: dict[str, Any],
    path: Union[str, Path] = CAMPAIGNS_PATH,
) -> bool:
    return _campaign_store(path).update(campaign_id, _normalize_campaign(values))


def delete_campaign(
    campaign_id: str, path: Union[str, Path] = CAMPAIGNS_PATH
) -> bool:
    return _campaign_store(path).delete(campaign_id)


def load_industry_templates(
    path: Union[str, Path] = INDUSTRY_TEMPLATES_PATH,
) -> list[dict[str, Any]]:
    return JsonStore(path).load()


def save_industry_template(
    template: dict[str, Any], path: Union[str, Path] = INDUSTRY_TEMPLATES_PATH
) -> None:
    JsonStore(path).add(template)


def update_industry_template(
    template_id: str,
    values: dict[str, Any],
    path: Union[str, Path] = INDUSTRY_TEMPLATES_PATH,
) -> bool:
    return JsonStore(path).update(template_id, values)


def delete_industry_template(
    template_id: str, path: Union[str, Path] = INDUSTRY_TEMPLATES_PATH
) -> bool:
    return JsonStore(path).delete(template_id)


def load_copy_templates(
    path: Union[str, Path] = COPY_TEMPLATES_PATH,
) -> list[dict[str, Any]]:
    return JsonStore(path).load()


def save_copy_template(
    template: dict[str, Any], path: Union[str, Path] = COPY_TEMPLATES_PATH
) -> None:
    JsonStore(path).add(template)


def update_copy_template(
    template_id: str,
    values: dict[str, Any],
    path: Union[str, Path] = COPY_TEMPLATES_PATH,
) -> bool:
    return JsonStore(path).update(template_id, values)


def delete_copy_template(
    template_id: str, path: Union[str, Path] = COPY_TEMPLATES_PATH
) -> bool:
    return JsonStore(path).delete(template_id)
