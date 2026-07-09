from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

try:  # Python 3.11+
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXTERNAL_ENV_FILE = Path(r"C:\Users\BNKFN\Desktop\bnk_practice\.env")

DART_KEY_NAMES = ("DART_API_KEY", "OPENDART_API_KEY", "OPEN_DART_API_KEY")
ECOS_KEY_NAMES = ("ECOS_API_KEY", "ECOS_AUTH_KEY", "BOK_ECOS_API_KEY", "BANK_OF_KOREA_API_KEY")

_SECRET_SOURCES: dict[str, str] = {}
_LOADED = False


@dataclass(frozen=True)
class EnvironmentLoadResult:
    loaded_files: tuple[str, ...]
    streamlit_secrets_loaded: bool
    project_root: str


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "nan"}:
        return None
    return text


def _set_if_absent(key: str, value: Any, source: str) -> bool:
    clean = _clean(value)
    if not key or clean is None:
        return False
    current = _clean(os.environ.get(key))
    if current is not None:
        _SECRET_SOURCES.setdefault(key, "os.environ")
        return False
    os.environ[key] = clean
    _SECRET_SOURCES.setdefault(key, source)
    return True


def _mark_existing_environment() -> None:
    for key, value in os.environ.items():
        if _looks_secret_name(key) and _clean(value) is not None:
            _SECRET_SOURCES.setdefault(key, "os.environ")


def _looks_secret_name(key: str) -> bool:
    return bool(re.search(r"(api[_-]?key|auth[_-]?key|secret|token|password)", key, re.IGNORECASE))


def _candidate_env_files() -> tuple[Path, ...]:
    candidates: list[Path] = []
    for env_name in ("ENV_FILE_PATH", "APP_ENV_FILE", "DOTENV_CONFIG_PATH"):
        value = _clean(os.environ.get(env_name))
        if value:
            candidates.append(Path(value).expanduser())
    candidates.extend(
        [
            DEFAULT_EXTERNAL_ENV_FILE,
            PROJECT_ROOT / ".env.local",
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / ".streamlit" / "secrets.toml",
        ]
    )

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(path)
    return tuple(deduped)


def _parse_dotenv_fallback(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return values
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            values[key] = value
    return values


def _load_dotenv_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    source = _source_label_for_path(path)
    if path.name == "secrets.toml":
        return _load_toml_secrets_file(path, source)

    before = {key for key, value in os.environ.items() if _clean(value) is not None}
    try:
        from dotenv import dotenv_values, load_dotenv
    except Exception:
        values = _parse_dotenv_fallback(path)
        loaded = False
        for key, value in values.items():
            loaded = _set_if_absent(key, value, source) or loaded
        return loaded

    try:
        load_dotenv(dotenv_path=path, override=False)
        values = dotenv_values(path)
    except Exception:
        values = _parse_dotenv_fallback(path)

    loaded = False
    for key, value in values.items():
        if _clean(value) is None:
            continue
        if key not in before and _clean(os.environ.get(key)) is not None:
            _SECRET_SOURCES.setdefault(str(key), source)
            loaded = True
        else:
            loaded = _set_if_absent(str(key), value, source) or loaded
    return loaded


def _source_label_for_path(path: Path) -> str:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    if path == PROJECT_ROOT / ".streamlit" / "secrets.toml" or path.name == "secrets.toml":
        return ".streamlit/secrets.toml"
    for env_name in ("ENV_FILE_PATH", "APP_ENV_FILE", "DOTENV_CONFIG_PATH"):
        value = _clean(os.environ.get(env_name))
        if value:
            try:
                if Path(value).expanduser().resolve() == resolved:
                    return env_name
            except Exception:
                pass
    if resolved == DEFAULT_EXTERNAL_ENV_FILE.resolve():
        return "default_external_env_file"
    if resolved == (PROJECT_ROOT / ".env.local").resolve():
        return "project_root:.env.local"
    if resolved == (PROJECT_ROOT / ".env").resolve():
        return "project_root:.env"
    return str(resolved)


def _load_toml_secrets_file(path: Path, source: str) -> bool:
    if tomllib is None:
        return False
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    loaded = False
    for key, value in raw.items():
        if isinstance(value, (str, int, float, bool)):
            loaded = _set_if_absent(str(key), value, source) or loaded
    return loaded


def _load_streamlit_secrets() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False

    loaded = False
    try:
        keys = list(st.secrets.keys())
    except Exception:
        return False
    for key in keys:
        try:
            value = st.secrets[key]
        except Exception:
            continue
        if isinstance(value, (str, int, float, bool)):
            loaded = _set_if_absent(str(key), value, "st.secrets") or loaded
    return loaded


def load_environment() -> EnvironmentLoadResult:
    global _LOADED
    if _LOADED:
        return EnvironmentLoadResult(
            loaded_files=tuple(sorted({source for source in _SECRET_SOURCES.values() if source not in {"os.environ", "st.secrets"}})),
            streamlit_secrets_loaded=any(source == "st.secrets" for source in _SECRET_SOURCES.values()),
            project_root=str(PROJECT_ROOT),
        )

    _mark_existing_environment()
    streamlit_loaded = _load_streamlit_secrets()
    loaded_files: list[str] = []
    for path in _candidate_env_files():
        if _load_dotenv_file(path):
            loaded_files.append(_source_label_for_path(path))
    _LOADED = True
    return EnvironmentLoadResult(
        loaded_files=tuple(loaded_files),
        streamlit_secrets_loaded=streamlit_loaded,
        project_root=str(PROJECT_ROOT),
    )


def get_secret(*names: str, required: bool = True) -> str | None:
    _ = required
    for name in names:
        value = _clean(os.environ.get(name))
        if value is not None:
            _SECRET_SOURCES.setdefault(name, "os.environ")
            return value
    load_environment()
    for name in names:
        value = _clean(os.environ.get(name))
        if value is not None:
            return value
    return None


def get_dart_api_key() -> str | None:
    return get_secret(*DART_KEY_NAMES, required=False)


def get_ecos_api_key() -> str | None:
    return get_secret(*ECOS_KEY_NAMES, required=False)


def mask_secret(value: str | None) -> str:
    clean = _clean(value)
    if clean is None:
        return "missing"
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:2]}{'*' * max(4, len(clean) - 6)}{clean[-4:]}"


def _source_for_names(names: tuple[str, ...]) -> tuple[str | None, str | None]:
    load_environment()
    for name in names:
        if _clean(os.environ.get(name)) is not None:
            return name, _SECRET_SOURCES.get(name, "os.environ")
    return None, None


def check_required_secrets() -> dict[str, Any]:
    dart_name, dart_source = _source_for_names(DART_KEY_NAMES)
    ecos_name, ecos_source = _source_for_names(ECOS_KEY_NAMES)
    missing = []
    if dart_name is None:
        missing.append("DART/OPENDART")
    if ecos_name is None:
        missing.append("ECOS/BOK")
    return {
        "ok": not missing,
        "missing": tuple(missing),
        "dart": {"present": dart_name is not None, "name": dart_name, "source": dart_source},
        "ecos": {"present": ecos_name is not None, "name": ecos_name, "source": ecos_source},
    }


def describe_secret_status() -> dict[str, dict[str, str | bool | None]]:
    dart_name, dart_source = _source_for_names(DART_KEY_NAMES)
    ecos_name, ecos_source = _source_for_names(ECOS_KEY_NAMES)
    openai_name, openai_source = _source_for_names(("OPENAI_API_KEY",))
    return {
        "dart": {"present": dart_name is not None, "name": dart_name, "source": dart_source},
        "ecos": {"present": ecos_name is not None, "name": ecos_name, "source": ecos_source},
        "openai": {"present": openai_name is not None, "name": openai_name, "source": openai_source},
    }


def sanitize_secret_text(text: str) -> str:
    load_environment()
    sanitized = str(text)
    for names in (DART_KEY_NAMES, ECOS_KEY_NAMES, ("OPENAI_API_KEY", "KIS_APP_KEY", "KIS_APP_SECRET")):
        for name in names:
            value = _clean(os.environ.get(name))
            if value:
                sanitized = sanitized.replace(value, mask_secret(value))
    return sanitized
