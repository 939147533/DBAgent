from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import (
    DatabaseProfile,
    DatabaseProfilesPayload,
    DatabaseSettings,
    LLMProfile,
    LLMProfilesPayload,
    LLMSettings,
    PublicDatabaseProfile,
    PublicDatabaseProfilesPayload,
    PublicDatabaseSettings,
    PublicLLMProfile,
    PublicLLMProfilesPayload,
    PublicLLMSettings,
    SettingsPayload,
)

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


def _profile_id() -> str:
    return uuid4().hex


def _deserialize_database(data: dict[str, Any]) -> DatabaseSettings:
    copied = dict(data)
    copied["password"] = _decrypt(str(copied.get("password", "")))
    return DatabaseSettings(**copied)


def _deserialize_database_profile(data: dict[str, Any]) -> DatabaseProfile:
    copied = dict(data)
    copied["password"] = _decrypt(str(copied.get("password", "")))
    copied.setdefault("id", _profile_id())
    copied.setdefault("name", "Default database")
    return DatabaseProfile(**copied)


def _deserialize_llm(data: dict[str, Any]) -> LLMSettings:
    copied = dict(data)
    copied["api_key"] = _decrypt(str(copied.get("api_key", "")))
    return LLMSettings(**copied)


def _deserialize_llm_profile(data: dict[str, Any]) -> LLMProfile:
    copied = dict(data)
    copied["api_key"] = _decrypt(str(copied.get("api_key", "")))
    copied.setdefault("id", _profile_id())
    copied.setdefault("name", "Default model")
    return LLMProfile(**copied)


def _active_database(settings: SettingsPayload) -> DatabaseProfile:
    _ensure_database_profiles(settings)
    for profile in settings.database_profiles:
        if profile.id == settings.active_database_id:
            return profile
    settings.active_database_id = settings.database_profiles[0].id
    return settings.database_profiles[0]


def _active_llm(settings: SettingsPayload) -> LLMProfile:
    _ensure_llm_profiles(settings)
    for profile in settings.llm_profiles:
        if profile.id == settings.active_llm_id:
            return profile
    settings.active_llm_id = settings.llm_profiles[0].id
    return settings.llm_profiles[0]


def _ensure_database_profiles(settings: SettingsPayload) -> None:
    if settings.database_profiles:
        if not settings.active_database_id or all(profile.id != settings.active_database_id for profile in settings.database_profiles):
            settings.active_database_id = settings.database_profiles[0].id
        active = next(profile for profile in settings.database_profiles if profile.id == settings.active_database_id)
        settings.database = DatabaseSettings(**active.model_dump(exclude={"id", "name"}))
        return
    profile = DatabaseProfile(id=_profile_id(), name="Default database", **settings.database.model_dump())
    settings.database_profiles = [profile]
    settings.active_database_id = profile.id


def _ensure_llm_profiles(settings: SettingsPayload) -> None:
    if settings.llm_profiles:
        if not settings.active_llm_id or all(profile.id != settings.active_llm_id for profile in settings.llm_profiles):
            settings.active_llm_id = settings.llm_profiles[0].id
        active = next(profile for profile in settings.llm_profiles if profile.id == settings.active_llm_id)
        settings.llm = LLMSettings(**active.model_dump(exclude={"id", "name"}))
        return
    profile = LLMProfile(id=_profile_id(), name="Default model", **settings.llm.model_dump())
    settings.llm_profiles = [profile]
    settings.active_llm_id = profile.id


def load_settings() -> SettingsPayload:
    if not SETTINGS_FILE.exists():
        settings = SettingsPayload()
        _ensure_database_profiles(settings)
        _ensure_llm_profiles(settings)
        return settings
    raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    settings = SettingsPayload(
        database=_deserialize_database(raw.get("database", {})),
        llm=_deserialize_llm(raw.get("llm", {})),
        database_profiles=[
            _deserialize_database_profile(item)
            for item in raw.get("database_profiles", [])
            if isinstance(item, dict)
        ],
        active_database_id=str(raw.get("active_database_id", "")),
        llm_profiles=[
            _deserialize_llm_profile(item)
            for item in raw.get("llm_profiles", [])
            if isinstance(item, dict)
        ],
        active_llm_id=str(raw.get("active_llm_id", "")),
    )
    _ensure_database_profiles(settings)
    _ensure_llm_profiles(settings)
    return settings


def save_database_settings(settings: DatabaseSettings) -> SettingsPayload:
    current = load_settings()
    current.database = settings
    active = _active_database(current)
    current.database_profiles = [
        DatabaseProfile(id=profile.id, name=profile.name, **settings.model_dump()) if profile.id == active.id else profile
        for profile in current.database_profiles
    ]
    save_settings(current)
    return current


def save_llm_settings(settings: LLMSettings) -> SettingsPayload:
    current = load_settings()
    current.llm = settings
    active = _active_llm(current)
    current.llm_profiles = [
        LLMProfile(id=profile.id, name=profile.name, **settings.model_dump()) if profile.id == active.id else profile
        for profile in current.llm_profiles
    ]
    save_settings(current)
    return current


def save_database_profiles(payload: DatabaseProfilesPayload) -> SettingsPayload:
    current = load_settings()
    profiles = payload.profiles or [DatabaseProfile(id=_profile_id(), name="Default database")]
    existing = {profile.id: profile for profile in current.database_profiles}
    normalized: list[DatabaseProfile] = []
    for index, profile in enumerate(profiles, start=1):
        data = profile.model_dump()
        data["id"] = data["id"] or _profile_id()
        data["name"] = data["name"].strip() or f"Database {index}"
        if data["password"] == "********" and data["id"] in existing:
            data["password"] = existing[data["id"]].password
        normalized.append(DatabaseProfile(**data))
    current.database_profiles = normalized
    current.active_database_id = payload.active_id if any(profile.id == payload.active_id for profile in normalized) else normalized[0].id
    current.database = DatabaseSettings(**_active_database(current).model_dump(exclude={"id", "name"}))
    save_settings(current)
    return current


def save_llm_profiles(payload: LLMProfilesPayload) -> SettingsPayload:
    current = load_settings()
    profiles = payload.profiles or [LLMProfile(id=_profile_id(), name="Default model")]
    existing = {profile.id: profile for profile in current.llm_profiles}
    normalized: list[LLMProfile] = []
    for index, profile in enumerate(profiles, start=1):
        data = profile.model_dump()
        data["id"] = data["id"] or _profile_id()
        data["name"] = data["name"].strip() or f"Model {index}"
        if data["api_key"] == "********" and data["id"] in existing:
            data["api_key"] = existing[data["id"]].api_key
        normalized.append(LLMProfile(**data))
    current.llm_profiles = normalized
    current.active_llm_id = payload.active_id if any(profile.id == payload.active_id for profile in normalized) else normalized[0].id
    current.llm = LLMSettings(**_active_llm(current).model_dump(exclude={"id", "name"}))
    save_settings(current)
    return current


def save_settings(settings: SettingsPayload) -> None:
    _ensure_data_dir()
    _ensure_database_profiles(settings)
    _ensure_llm_profiles(settings)
    payload = {
        "database": _serialize_model(settings.database),
        "llm": _serialize_model(settings.llm),
        "database_profiles": [_serialize_model(profile) for profile in settings.database_profiles],
        "active_database_id": settings.active_database_id,
        "llm_profiles": [_serialize_model(profile) for profile in settings.llm_profiles],
        "active_llm_id": settings.active_llm_id,
    }
    SETTINGS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def public_database_settings(settings: DatabaseSettings) -> PublicDatabaseSettings:
    data = settings.model_dump()
    data["password"] = "********" if settings.password else ""
    return PublicDatabaseSettings(**data)


def public_database_profile(profile: DatabaseProfile) -> PublicDatabaseProfile:
    data = profile.model_dump()
    data["password"] = "********" if profile.password else ""
    return PublicDatabaseProfile(**data)


def public_database_profiles(settings: SettingsPayload) -> PublicDatabaseProfilesPayload:
    _ensure_database_profiles(settings)
    return PublicDatabaseProfilesPayload(
        active_id=settings.active_database_id,
        profiles=[public_database_profile(profile) for profile in settings.database_profiles],
    )


def public_llm_settings(settings: LLMSettings) -> PublicLLMSettings:
    data = settings.model_dump()
    data["api_key"] = "********" if settings.api_key else ""
    return PublicLLMSettings(**data)


def public_llm_profile(profile: LLMProfile) -> PublicLLMProfile:
    data = profile.model_dump()
    data["api_key"] = "********" if profile.api_key else ""
    return PublicLLMProfile(**data)


def public_llm_profiles(settings: SettingsPayload) -> PublicLLMProfilesPayload:
    _ensure_llm_profiles(settings)
    return PublicLLMProfilesPayload(
        active_id=settings.active_llm_id,
        profiles=[public_llm_profile(profile) for profile in settings.llm_profiles],
    )
