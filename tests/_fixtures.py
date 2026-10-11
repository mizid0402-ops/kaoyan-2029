"""Shared test fixtures for legacy-shaped inputs and fixed-source reads."""

from __future__ import annotations

import dataclasses
import copy
import subprocess
from pathlib import Path
from typing import Any


@dataclasses.dataclass(frozen=True)
class _LegacyReviewPolicy:
    self_rating_mode: str = "strict"


class LegacyConfigView:
    """Expose the pre-B6 field name and pre-FSRS review policy only to legacy baselines."""

    def __init__(self, config: Any) -> None:
        self._config = config

    def __getattr__(self, name: str) -> Any:
        if name == "total_daily_minutes":
            return self._config.default_daily_minutes
        return getattr(self._config, name)

    def as_dataclass(self) -> Any:
        fields = dataclasses.fields(self._config)
        legacy_fields = [
            field for field in fields if field.name != "default_daily_minutes"
        ]
        values = {
            field.name: getattr(self._config, field.name) for field in legacy_fields
        }
        values["total_daily_minutes"] = self._config.default_daily_minutes
        # Pre-FSRS baselines only knew review_policy.self_rating_mode; a default
        # ladder config must look exactly like that to them (config_to_mapping does the same).
        if self._config.review_policy.algorithm == "ladder":
            values["review_policy"] = _LegacyReviewPolicy(
                self._config.review_policy.self_rating_mode
            )
        legacy_type = dataclasses.make_dataclass(
            "LegacyConfig",
            [(field.name, Any) for field in legacy_fields]
            + [("total_daily_minutes", int)],
        )
        legacy_type.default_daily_minutes = property(
            lambda instance: instance.total_daily_minutes
        )
        legacy = legacy_type(**values)
        if "default_daily_minutes" in {
            field.name for field in dataclasses.fields(legacy)
        }:
            raise AssertionError("legacy baseline view still exposes the renamed field")
        legacy.review_hard_cap_minutes = self._config.review_hard_cap_minutes
        legacy.review_target_minutes = self._config.review_target_minutes
        legacy.subject = self._config.subject
        legacy.active_subjects = self._config.active_subjects
        legacy.weight_of = self._config.weight_of
        return legacy


def git_source(
    testcase: Any, repository: Path, commit: str, relative_path: str
) -> str:
    """Read a UTF-8 source file from a pinned commit."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    testcase.assertEqual(
        result.returncode, 0, result.stderr.decode("utf-8", errors="replace")
    )
    source = result.stdout.decode("utf-8")
    testcase.assertTrue(source)
    return source
def set_nested_value(document: dict[str, Any], path: tuple[Any, ...], value: Any) -> None:
    """Set one generated test input field, creating missing mapping parents."""
    node: Any = document
    for key in path[:-1]:
        if isinstance(node, dict) and key not in node:
            node[key] = {}
        node = node[key]
    node[path[-1]] = value


SectionError = tuple[str, list[tuple[tuple[Any, ...], Any]]]


def cross_section_error_pairs(
    seed: dict[str, Any], errors: list[SectionError], prefix: str,
) -> list[tuple[str, Any, bool]]:
    """Build paired section failures used only to probe validation order."""
    variants: list[tuple[str, Any, bool]] = []
    for first in range(len(errors)):
        for second in range(first + 1, len(errors)):
            first_name, first_edits = errors[first]
            second_name, second_edits = errors[second]
            if {path for path, _ in first_edits} & {path for path, _ in second_edits}:
                continue
            document = copy.deepcopy(seed)
            for path, value in first_edits + second_edits:
                set_nested_value(document, path, value)
            variants.append((f"{prefix}-cross-{first_name}-{second_name}", document, False))
    return variants
