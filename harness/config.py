"""Typed-ish config loader. All experiment knobs live in config.yaml, never in source."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    text = path.read_text()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:  # pragma: no cover - fallback for minimal envs
        # Minimal YAML subset parser is risky; require pyyaml for real runs.
        raise RuntimeError(
            "pyyaml is required to read config.yaml. Run: pip install pyyaml"
        )


def get(cfg: Dict[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
