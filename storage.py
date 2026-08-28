import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Union


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CAMPAIGNS_PATH = DATA_DIR / "campaigns.json"
COPY_TEMPLATES_PATH = DATA_DIR / "templates.json"
INDUSTRY_TEMPLATES_PATH = DATA_DIR / "industry_templates.json"
INDUSTRY_TABLE = "industry_templates"
MIGRATIONS_TABLE = "app_migrations"
INDUSTRY_JSON_MIGRATION = "industry_templates_json_v1"


class IndustryStorageError(RuntimeError):
    """Raised when permanent industry storage is unavailable."""


def _industry_json_test_backend() -> bool:
    """Allow deterministic UI tests without weakening production persistence."""
    return os.environ.get("OMNICHAT_TEST_INDUSTRY_JSON") == "1"


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
    stored_points = normalized.get("activity_points")
    if isinstance(stored_points, str):
        stored_points = [
            line.strip().lstrip("-•・ ")
            for line in stored_points.splitlines()
            if line.strip().lstrip("-•・ ")
        ]
    elif isinstance(stored_points, list):
        stored_points = [str(item).strip() for item in stored_points if str(item).strip()]
    else:
        stored_points = []
    if not stored_points:
        stored_points = [
            str(normalized.get(f"activity_point_{index}", "")).strip()
            for index in range(1, 5)
            if str(normalized.get(f"activity_point_{index}", "")).strip()
        ]
    normalized["activity_points"] = stored_points
    defaults = {
        "event_time": "",
        "location": "",
        "address": "",
        "primary_industry": normalized.get("suitable_industries", ""),
        "summary": "",
        "introduction": normalized.get("highlights", ""),
        "development_hook": "",
        "activity_point_1": "",
        "activity_point_2": "",
        "activity_point_3": "",
        "activity_point_4": "",
        "subject_a": normalized.get("email_title_a", ""),
        "subject_b": normalized.get("email_title_b", ""),
        "subject_c": normalized.get("email_title_c", ""),
        "selected_subject": "",
        "subject_generation_round": 0,
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


def _industry_storage_error(action: str, error: Exception) -> IndustryStorageError:
    message = (
        f"產業別資料庫無法{action}。資料沒有改寫至本機 JSON，請檢查 Supabase "
        f"連線、資料表與 Streamlit Secrets。原始錯誤：{error}"
    )
    try:
        import streamlit as st

        st.error(message)
    except Exception:
        pass
    return IndustryStorageError(message)


def _supabase_credentials() -> tuple[str, str]:
    try:
        import streamlit as st

        settings = st.secrets["supabase"]
        url = str(settings["url"]).strip()
        secret_key = str(settings["secret_key"]).strip()
    except Exception as error:
        raise _industry_storage_error("連線", error) from error
    if not url or not secret_key:
        raise _industry_storage_error("連線", ValueError("Supabase Secrets 不完整"))
    if not secret_key.startswith("sb_secret_"):
        raise _industry_storage_error(
            "連線",
            ValueError(
                "secret_key 必須使用 Supabase Secret key（sb_secret_ 開頭），"
                "不可使用 Publishable／anon key"
            ),
        )
    return url, secret_key


@lru_cache(maxsize=1)
def _create_supabase_client(url: str, secret_key: str):
    try:
        from supabase import ClientOptions, create_client

        return create_client(
            url,
            secret_key,
            options=ClientOptions(
                auto_refresh_token=False,
                persist_session=False,
            ),
        )
    except Exception as error:
        raise _industry_storage_error("建立連線", error) from error


def _supabase_client():
    return _create_supabase_client(*_supabase_credentials())


def _industry_row(template: dict[str, Any]) -> dict[str, Any]:
    payload = dict(template)
    template_id = str(payload.get("id", "")).strip()
    industry_name = str(payload.get("industry_name", "")).strip()
    if not template_id or not industry_name:
        raise ValueError("產業資料必須包含 id 與 industry_name")
    payload["id"] = template_id
    payload["industry_name"] = industry_name
    return {
        "id": template_id,
        "industry_name": industry_name,
        "payload": payload,
    }


def _migrate_industry_json_once(client) -> None:
    migration = (
        client.table(MIGRATIONS_TABLE)
        .select("key")
        .eq("key", INDUSTRY_JSON_MIGRATION)
        .limit(1)
        .execute()
    )
    if migration.data:
        return

    backup_records = JsonStore(INDUSTRY_TEMPLATES_PATH).load()
    existing = client.table(INDUSTRY_TABLE).select("id").execute()
    existing_ids = {str(row["id"]) for row in (existing.data or [])}
    missing_rows = [
        _industry_row(record)
        for record in backup_records
        if str(record.get("id", "")) not in existing_ids
    ]
    if missing_rows:
        client.table(INDUSTRY_TABLE).upsert(
            missing_rows, on_conflict="id", ignore_duplicates=True
        ).execute()
    client.table(MIGRATIONS_TABLE).upsert(
        {"key": INDUSTRY_JSON_MIGRATION},
        on_conflict="key",
        ignore_duplicates=True,
    ).execute()


def _load_supabase_industries() -> list[dict[str, Any]]:
    try:
        client = _supabase_client()
        _migrate_industry_json_once(client)
        response = (
            client.table(INDUSTRY_TABLE)
            .select("payload")
            .order("industry_name")
            .execute()
        )
        return [dict(row["payload"]) for row in (response.data or [])]
    except IndustryStorageError:
        raise
    except Exception as error:
        raise _industry_storage_error("讀取", error) from error


def load_industry_templates(
    path: Union[str, Path, None] = None,
) -> list[dict[str, Any]]:
    if path is None and _industry_json_test_backend():
        path = INDUSTRY_TEMPLATES_PATH
    if path is not None:
        return JsonStore(path).load()
    return _load_supabase_industries()


def save_industry_template(
    template: dict[str, Any], path: Union[str, Path, None] = None
) -> None:
    if path is None and _industry_json_test_backend():
        path = INDUSTRY_TEMPLATES_PATH
    if path is not None:
        JsonStore(path).add(template)
        return
    try:
        _supabase_client().table(INDUSTRY_TABLE).insert(
            _industry_row(template)
        ).execute()
    except IndustryStorageError:
        raise
    except Exception as error:
        raise _industry_storage_error("新增", error) from error


def update_industry_template(
    template_id: str,
    values: dict[str, Any],
    path: Union[str, Path, None] = None,
) -> bool:
    if path is None and _industry_json_test_backend():
        path = INDUSTRY_TEMPLATES_PATH
    if path is not None:
        return JsonStore(path).update(template_id, values)
    try:
        client = _supabase_client()
        current = (
            client.table(INDUSTRY_TABLE)
            .select("payload")
            .eq("id", template_id)
            .limit(1)
            .execute()
        )
        if not current.data:
            return False
        merged = {**dict(current.data[0]["payload"]), **values, "id": template_id}
        client.table(INDUSTRY_TABLE).update(_industry_row(merged)).eq(
            "id", template_id
        ).execute()
        return True
    except IndustryStorageError:
        raise
    except Exception as error:
        raise _industry_storage_error("更新", error) from error


def delete_industry_template(
    template_id: str, path: Union[str, Path, None] = None
) -> bool:
    if path is None and _industry_json_test_backend():
        path = INDUSTRY_TEMPLATES_PATH
    if path is not None:
        return JsonStore(path).delete(template_id)
    try:
        client = _supabase_client()
        current = (
            client.table(INDUSTRY_TABLE)
            .select("id")
            .eq("id", template_id)
            .limit(1)
            .execute()
        )
        if not current.data:
            return False
        client.table(INDUSTRY_TABLE).delete().eq("id", template_id).execute()
        return True
    except IndustryStorageError:
        raise
    except Exception as error:
        raise _industry_storage_error("刪除", error) from error


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
