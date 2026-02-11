"""
config/loader.py – Load, validate, and merge YAML configuration.

Provides a nested-attribute-access wrapper (``Cfg``) so that station code
can write ``cfg.S3.cool_remove_time`` instead of ``cfg["S3"]["cool_remove_time"]``.
"""

from __future__ import annotations

import copy
import pathlib
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Attribute-access wrapper
# ---------------------------------------------------------------------------

class Cfg:
    """Recursive attribute wrapper around a dict tree."""

    def __init__(self, d: dict):
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, Cfg(v))
            else:
                setattr(self, k, v)

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"Cfg({items})"

    def to_dict(self) -> dict:
        out: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            out[k] = v.to_dict() if isinstance(v, Cfg) else v
        return out


# ---------------------------------------------------------------------------
# Deep merge
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into a copy of *base*."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DEFAULT_PATH = pathlib.Path(__file__).parent / "defaults.yaml"


def load_config(
    defaults: str | pathlib.Path = _DEFAULT_PATH,
    overrides: str | pathlib.Path | dict | None = None,
) -> Cfg:
    """Load the default YAML config, optionally deep-merge an override file/dict.

    Parameters
    ----------
    defaults : path-like
        Path to ``defaults.yaml``.
    overrides : path-like, dict, or None
        Either a YAML file path or a dict of overrides.  Keys are deep-merged
        on top of the defaults.

    Returns
    -------
    Cfg
        Nested-attribute config object.
    """
    with open(defaults, "r", encoding="utf-8") as f:
        base: dict = yaml.safe_load(f)

    if overrides is not None:
        if isinstance(overrides, dict):
            ovr = overrides
        else:
            with open(overrides, "r", encoding="utf-8") as f:
                ovr = yaml.safe_load(f) or {}
            if not isinstance(ovr, dict):
                raise ValueError(f"Override file must contain a YAML mapping, got {type(ovr)}")
        base = _deep_merge(base, ovr)

    return Cfg(base)
