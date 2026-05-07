from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH_TOML = Path.home() / ".dont-commit-me.toml"
CONFIG_PATH_JSON = Path.home() / ".dont-commit-me.json"


class MisconfiguredRule(Exception):
    pass


@dataclass
class LineRule:
    extensions: list[str]
    match: str = ""
    start_with: list[str] = field(default_factory=list)
    contains: list[str] = field(default_factory=list)


@dataclass
class FileRule:
    paths: list[str]
    no_changes: bool = False
    match: str = ""
    contains: list[str] = field(default_factory=list)


@dataclass
class Config:
    stop_on_catch: bool
    line_rules: list[LineRule]
    file_rules: list[FileRule]
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def _find_config() -> tuple[Path, str] | None:
    if CONFIG_PATH_TOML.exists():
        return CONFIG_PATH_TOML, "toml"
    if CONFIG_PATH_JSON.exists():
        return CONFIG_PATH_JSON, "json"
    return None


def _parse(raw: dict) -> Config:
    cfg = raw.get("config", {})

    config_warnings: list[str] = []
    line_rules = []
    for i, r in enumerate(raw.get("line_rule", []), start=1):
        if not r.get("extensions"):
            raise MisconfiguredRule(f"[[line_rule]] #{i}: 'extensions' is required.")
        if not r.get("match") and not r.get("contains"):
            raise MisconfiguredRule(f"[[line_rule]] #{i}: define 'match' or 'contains'.")
        line_rules.append(LineRule(
            extensions=r["extensions"],
            match=r.get("match", ""),
            start_with=r.get("start_with", []),
            contains=r.get("contains", []),
        ))

    file_rules = []
    for i, r in enumerate(raw.get("file_rule", []), start=1):
        if not r.get("paths"):
            raise MisconfiguredRule(f"[[file_rule]] #{i}: 'paths' is required.")
        no_changes = r.get("no_changes", False)
        has_match = r.get("match") or r.get("contains")
        if no_changes and has_match:
            config_warnings.append(f"⚠️  [[file_rule]] #{i}: 'no_changes=true' ignores 'match' and 'contains'.")
        if not no_changes and not has_match:
            raise MisconfiguredRule(f"[[file_rule]] #{i}: define 'no_changes', 'match' or 'contains'.")
        file_rules.append(FileRule(
            paths=r["paths"],
            no_changes=no_changes,
            match=r.get("match", ""),
            contains=r.get("contains", []),
        ))

    return Config(
        stop_on_catch=cfg.get("stop_on_catch", False),
        line_rules=line_rules,
        file_rules=file_rules,
        warnings=config_warnings,
    )


def load_config() -> Config | None:
    result = _find_config()
    if result is None:
        return None
    path, fmt = result
    try:
        if fmt == "toml":
            raw = tomllib.loads(path.read_text())
        else:
            raw = json.loads(path.read_text())
    except (tomllib.TOMLDecodeError, json.JSONDecodeError) as e:
        raise MisconfiguredRule(f"Failed to parse {path.name}: {e}") from e
    return _parse(raw)