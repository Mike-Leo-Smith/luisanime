from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


SECRET_KEY_NAMES = {"api_key", "secret_key", "access_key", "token", "password"}
SECRET_ENV_HINTS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "PASS")
MASK_SENTINEL = "__MASKED__"


def _mask(value: str) -> str:
    if not value:
        return ""
    if value.startswith("ENV:") or value.startswith("MISSING_ENV_"):
        return value
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def _is_secret_env(name: str) -> bool:
    n = name.upper()
    return any(h in n for h in SECRET_ENV_HINTS)


def parse_env_file(path: Path, reveal: bool = False) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        secret = _is_secret_env(key)
        out.append({
            "key": key,
            "value": (value if (reveal or not secret) else _mask(value)),
            "secret": secret,
            "has_value": bool(value),
        })
    return out


def write_env_file(path: Path, items: List[Dict[str, Any]], existing: List[Dict[str, Any]]) -> None:
    existing_map = {e["key"]: e["value"] for e in existing}
    lines = ["# Managed by AFP Admin UI"]
    seen = set()
    for it in items:
        key = (it.get("key") or "").strip()
        if not key:
            continue
        seen.add(key)
        val = it.get("value", "")
        if val == MASK_SENTINEL or (isinstance(val, str) and "*" in val and val == _mask(existing_map.get(key, ""))):
            val = existing_map.get(key, "")
        lines.append(f"{key}={val}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mask_config_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in SECRET_KEY_NAMES and isinstance(v, str) and v and not v.startswith("ENV:"):
                out[k] = _mask(v)
            else:
                out[k] = mask_config_secrets(v)
        return out
    if isinstance(obj, list):
        return [mask_config_secrets(x) for x in obj]
    return obj


def unmask_config(new_obj: Any, old_obj: Any) -> Any:
    if isinstance(new_obj, dict) and isinstance(old_obj, dict):
        out = {}
        for k, v in new_obj.items():
            if k in SECRET_KEY_NAMES and isinstance(v, str):
                if v == MASK_SENTINEL or (v == old_obj.get(k) and old_obj.get(k) and "*" in str(old_obj.get(k))):
                    out[k] = old_obj.get(k, v)
                else:
                    out[k] = v
            else:
                out[k] = unmask_config(v, old_obj.get(k))
        return out
    if isinstance(new_obj, list):
        return new_obj
    return new_obj


def load_config_file(path: Path) -> Tuple[Dict[str, Any], str]:
    if not path.exists():
        return {}, ""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    return data, raw


def save_config_file(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def save_config_raw(path: Path, raw: str) -> None:
    yaml.safe_load(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
