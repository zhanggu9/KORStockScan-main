"""Configuration loading for the sniper engine."""

import json
import os
import re
from collections.abc import Mapping

from src.utils.constants import CONFIG_PATH, DEV_PATH
from src.utils.logger import log_error


_OPENAI_API_KEY_NAME = re.compile(r"^OPENAI_API_KEY(?:_\d+)?$")


def _openai_keys_from_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return explicitly exported OpenAI keys in the engine's config shape.

    The main engine consumes ``CONF`` rather than reading ``os.environ`` at
    startup.  Keep the environment boundary here so a shell-exported key is
    available without writing a credential into the JSON configuration file.
    ``OPENAI_API_KEYS`` is accepted as a comma-separated convenience form.
    """
    source = os.environ if environ is None else environ
    keys: dict[str, str] = {}
    primary = str(source.get("OPENAI_API_KEY") or "").strip()
    if primary:
        keys["OPENAI_API_KEY"] = primary

    indexed_names = sorted(
        (
            name
            for name in source
            if _OPENAI_API_KEY_NAME.fullmatch(str(name))
            and name != "OPENAI_API_KEY"
        ),
        key=lambda name: int(str(name).rsplit("_", 1)[1]),
    )
    for name in indexed_names:
        value = str(source.get(name) or "").strip()
        if value:
            keys[str(name)] = value

    if not keys:
        raw_values = str(source.get("OPENAI_API_KEYS") or "")
        values = [value.strip() for value in raw_values.split(",") if value.strip()]
        for index, value in enumerate(values):
            name = "OPENAI_API_KEY" if index == 0 else f"OPENAI_API_KEY_{index + 1}"
            keys[name] = value
    return keys


def _merge_openai_environment(config: dict, environ: Mapping[str, str] | None = None) -> dict:
    """Give explicitly exported OpenAI credentials precedence over file keys."""
    environment_keys = _openai_keys_from_environment(environ)
    if not environment_keys:
        return config
    merged = {
        name: value
        for name, value in config.items()
        if not str(name).startswith("OPENAI_API_KEY")
    }
    merged.update(environment_keys)
    return merged


def load_system_config(environ: Mapping[str, str] | None = None):
    target = CONFIG_PATH if CONFIG_PATH.exists() else DEV_PATH
    try:
        with open(target, "r", encoding="utf-8") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                raise ValueError("system config root must be an object")
            return _merge_openai_environment(config, environ)
    except Exception as exc:
        log_error(f"Config load failed: {exc}")
        return {}


CONF = load_system_config()
