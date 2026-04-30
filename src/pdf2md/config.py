from __future__ import annotations

from pathlib import Path
import tomllib


REQUIRED_BACKEND_KEYS = {"enabled", "runner", "env_name", "script"}


def load_backend_config(path: Path) -> dict:
    with path.open("rb") as f:
        config = tomllib.load(f)
    validate_backend_config(config)
    return config


def get_enabled_backends(config: dict) -> dict:
    backends = config.get("backends", {})
    return {name: data for name, data in backends.items() if data.get("enabled") is True}


def validate_backend_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError("Config must be a TOML table.")

    settings = config.get("settings", {})
    if settings and not isinstance(settings, dict):
        raise ValueError("[settings] must be a TOML table.")

    backends = config.get("backends")
    if backends is None or not isinstance(backends, dict):
        raise ValueError("[backends] must be defined as a TOML table.")

    for name, backend in backends.items():
        if not isinstance(backend, dict):
            raise ValueError(f"[backends.{name}] must be a TOML table.")
        missing = REQUIRED_BACKEND_KEYS - set(backend.keys())
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"[backends.{name}] missing required keys: {missing_list}")
        if backend.get("runner") != "conda":
            raise ValueError(f"[backends.{name}].runner must be 'conda'.")
        if not isinstance(backend.get("enabled"), bool):
            raise ValueError(f"[backends.{name}].enabled must be true/false.")
        if not isinstance(backend.get("env_name"), str) or not backend["env_name"].strip():
            raise ValueError(f"[backends.{name}].env_name must be a non-empty string.")
        if not isinstance(backend.get("script"), str) or not backend["script"].strip():
            raise ValueError(f"[backends.{name}].script must be a non-empty string.")
        if "args" in backend and not isinstance(backend["args"], dict):
            raise ValueError(f"[backends.{name}].args must be a table.")
        if "env" in backend and not isinstance(backend["env"], dict):
            raise ValueError(f"[backends.{name}].env must be a table.")
        if "extra_args" in backend and not isinstance(backend["extra_args"], list):
            raise ValueError(f"[backends.{name}].extra_args must be an array.")
