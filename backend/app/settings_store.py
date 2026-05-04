from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .models import DatabaseSettings, LLMSettings, PublicDatabaseSettings, PublicLLMSettings, SettingsPayload

DATA_DIR = Path(__file__).resolve().parents[1] / ".data"
SETTINGS_FILE = DATA_DIR / "settings.json"
KEY_FILE = DATA_DIR / "secret.key"
SECRET_FIELDS = {"password", "api_key"}


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_fernet() -> Any | None:
    try:
        from cryptography.fernet import Fernet
    except Exception:
        return None
    _ensure_data_dir()
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())
    return Fernet(KEY_FILE.read_bytes())


def _encrypt(value: str) -> str:
    if not value:
        return ""
    fernet = _load_fernet()
    if fernet is None:
        return "b64:" + base64.b64encode(value.encode("utf-8")).decode("ascii")
    return "fernet:" + fernet.encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str) -> str:
    if not value:
        return ""
    if value.startswith("fernet:"):
        fernet = _load_fernet()
        if fernet is None:
            return ""
        return fernet.decrypt(value.removeprefix("fernet:").encode("ascii")).decode("utf-8")
    if value.startswith("b64:"):
        return base64.b64decode(value.removeprefix("b64:").encode("ascii")).decode("utf-8")
    return value


def _serialize_model(model: DatabaseSettings | LLMSettings) -> dict[str, Any]:
    data = model.model_dump(mode="json")
    for field in SECRET_FIELDS:
        if field in data:
            data[field] = _encrypt(data[field])
    return data


def _deserialize_database(data: dict[str, Any]) -> DatabaseSettings:
    copied = dict(data)
    copied["password"] = _decrypt(str(copied.get("password", "")))
    return DatabaseSettings(**copied)


def _deserialize_llm(data: dict[str, Any]) -> LLMSettings:
    copied = dict(data)
    copied["api_key"] = _decrypt(str(copied.get("api_key", "")))
    return LLMSettings(**copied)


def load_settings() -> SettingsPayload:
    if not SETTINGS_FILE.exists():
        return SettingsPayload()
    raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    return SettingsPayload(
        database=_deserialize_database(raw.get("database", {})),
        llm=_deserialize_llm(raw.get("llm", {})),
    )


def save_database_settings(settings: DatabaseSettings) -> SettingsPayload:
    current = load_settings()
    current.database = settings
    save_settings(current)
    return current


def save_llm_settings(settings: LLMSettings) -> SettingsPayload:
    current = load_settings()
    current.llm = settings
    save_settings(current)
    return current


def save_settings(settings: SettingsPayload) -> None:
    _ensure_data_dir()
    payload = {
        "database": _serialize_model(settings.database),
        "llm": _serialize_model(settings.llm),
    }
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def public_database_settings(settings: DatabaseSettings) -> PublicDatabaseSettings:
    data = settings.model_dump()
    data["password"] = "********" if settings.password else ""
    return PublicDatabaseSettings(**data)


def public_llm_settings(settings: LLMSettings) -> PublicLLMSettings:
    data = settings.model_dump()
    data["api_key"] = "********" if settings.api_key else ""
    return PublicLLMSettings(**data)
