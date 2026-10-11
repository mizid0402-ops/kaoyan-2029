"""M8 config and domain models; see ``contracts/config.md``.

Public config interfaces: :func:`load_config`, :func:`validate_config`, and
:func:`scale_minutes`. This module also owns domain models and semantic validation.

Design rules enforced here (see docs/评审结论与实施契约.md):

1. This module guards *both* shape and cross-field semantics. There is no
   separate JSON Schema layer: every mapping (config root, each subject, the
   reviews root, each review item, each ``schedule`` block) is checked
   against an explicit allowed-key set, so an unknown or misspelled field is
   rejected instead of being silently ignored or defaulted. Semantic checks
   that a plain shape check cannot express (for example "active weights must
   sum to 1") run on top of that.
2. Every rejection carries a machine-readable path so the caller can point at
   the exact offending field instead of a generic "invalid config".
3. Nothing in this module reads or writes the study workspace. It is pure.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:  # pragma: no cover - exercised only when PyYAML is absent
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

__all__ = [
    "ContractError",
    "SubjectBudget",
    "ReviewPolicy",
    "KaoyanConfig",
    "ReviewSchedule",
    "ReviewItem",
    "config_to_mapping",
    "load_config",
    "load_review_items",
    "load_yaml_text",
    "scale_minutes",
    "validate_items_against_config",
    "WEIGHT_TOLERANCE",
]

# Weights are compared with an explicit tolerance because they are authored as
# decimals in YAML and 0.4 + 0.2 + 0.4 does not sum to exactly 1.0 in binary
# floating point.
WEIGHT_TOLERANCE = 1e-6

VALID_REVIEW_STATES = ("queued", "scheduled", "suspended", "retired")
VALID_GRANULARITIES = (
    "concept",
    "procedure",
    "question_pattern",
    "error_pattern",
    "vocabulary_batch",
)
VALID_SCHEDULE_MODES = ("fixed_bootstrap", "sm2_lite", "fsrs")
VALID_SELF_RATINGS = ("unknown", "vague", "basic", "fluent")

REVIEWS_SCHEMA_VERSION = 1

CONFIG_ROOT_KEYS = frozenset(
    {
        "schema_version",
        "project_id",
        "default_daily_minutes",
        "review_reserve_ratio",
        "hard_max_ratio",
        "subjects",
        "review_policy",
    }
)
SUBJECT_KEYS = frozenset({"subject_id", "display_name", "weight", "active", "min_daily_minutes"})
SCHEDULE_KEYS = frozenset({
    "mode", "phase", "interval_days", "ease_factor", "repetitions", "lapses",
    "stability", "difficulty", "fsrs_reviewed_on",
})
REVIEW_ITEM_KEYS = frozenset(
    {
        "review_id",
        "revision",
        "subject_id",
        "knowledge_point_id",
        "title",
        "granularity",
        "state",
        "estimated_minutes",
        "introduced_on",
        "due_date",
        "last_reviewed_on",
        "schedule",
        "defer_count",
        "last_quality",
        "self_rating",
    }
)
REVIEWS_ROOT_KEYS = frozenset({"schema_version", "items"})

# Single review passes are capped so that one oversized item can never starve
# the rest of the queue: an item above this cost must be split before import.
MAX_SINGLE_PASS_MINUTES = 30


class ContractError(ValueError):
    """Raised when a contract file is structurally or semantically invalid.

    ``path`` is a JSON-Pointer-ish location such as
    ``subjects[1].weight`` or ``schedule.interval_days``.
    """

    def __init__(self, message: str, path: str = "") -> None:
        self.message = message
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


# --------------------------------------------------------------------------
# small shared helpers
# --------------------------------------------------------------------------


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"expected a mapping, got {type(value).__name__}", path)
    return value


def _reject_unknown_keys(node: Mapping[str, Any], allowed: frozenset[str], path: str) -> None:
    """Fail closed on any key outside ``allowed`` instead of ignoring it.

    A typo'd or unsupported field (``min_daily_minute`` instead of
    ``min_daily_minutes``) must not be silently dropped or defaulted -- it
    has to surface as a contract violation with the exact field path.

    A non-string key (YAML ``1: x``) is never an allowed field. It is reported first,
    because sorting it together with string keys raised ``TypeError`` and a lone one
    left an integer in ``ContractError.path`` (round 151 §5, WP-R3).
    """
    non_string = [key for key in node.keys() if not isinstance(key, str)]
    unknown = non_string or sorted(set(node.keys()) - allowed)
    if unknown:
        key = unknown[0]
        field_path = f"{path}.{key}" if path else str(key)
        raise ContractError(f"unknown field {key!r}", field_path)


def _require_str(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ContractError("expected a non-empty string", path)
    return value


def _require_text(value: Any, path: str) -> str:
    """Like ``_require_str`` but tolerates YAML scalars such as ``408``.

    Display names are human-facing labels, so a bare integer in YAML
    (``display_name: 408``) is a formatting accident, not a contract
    violation. Identifiers and enum values stay strict.
    """
    if isinstance(value, bool):
        raise ContractError("expected a non-empty string", path)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _require_str(value, path)


def _require_int(
    value: Any,
    path: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"expected an integer, got {type(value).__name__}", path)
    if minimum is not None and value < minimum:
        raise ContractError(f"must be >= {minimum}, got {value}", path)
    if maximum is not None and value > maximum:
        raise ContractError(f"must be <= {maximum}, got {value}", path)
    return value


def _require_float(
    value: Any,
    path: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    tolerance: float = WEIGHT_TOLERANCE,
) -> float:
    """Validate a finite float, optionally inside ``[minimum, maximum]``.

    ``tolerance`` slackens both bounds. It defaults to ``WEIGHT_TOLERANCE``
    because weights are authored as decimals that do not close exactly in
    binary floating point. Pass ``tolerance=0.0`` for a field where a value
    outside the bound is *semantically* meaningless rather than merely
    imprecise -- a ratio is the example: ``review_reserve_ratio: -0.000001``
    used to be accepted and produced a soft quota of **-1 minutes**, a
    negative duration in an audit record.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"expected a number, got {type(value).__name__}", path)
    value = float(value)
    if not math.isfinite(value):
        # NaN compares false against every bound below, and +/-inf only get
        # caught by luck when a bound happens to be configured; check
        # finiteness explicitly instead of relying on that side effect.
        raise ContractError(f"expected a finite number, got {value}", path)
    if minimum is not None and value < minimum - tolerance:
        raise ContractError(f"must be >= {minimum}, got {value}", path)
    if maximum is not None and value > maximum + tolerance:
        raise ContractError(f"must be <= {maximum}, got {value}", path)
    return value


def _require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"expected a boolean, got {type(value).__name__}", path)
    return value


def _parse_date(value: Any, path: str, *, optional: bool = False) -> date | None:
    if value is None:
        if optional:
            return None
        raise ContractError("expected an ISO date (YYYY-MM-DD)", path)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ContractError(f"expected an ISO date (YYYY-MM-DD), got {value!r}", path) from exc
    raise ContractError(f"expected an ISO date (YYYY-MM-DD), got {type(value).__name__}", path)


def _parse_timestamp(value: Any, path: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise ContractError(f"expected an ISO-8601 timestamp, got {value!r}", path) from exc
    raise ContractError(f"expected an ISO-8601 timestamp, got {type(value).__name__}", path)


class _DuplicateKeyError(Exception):
    """Internal signal from ``_StrictSafeLoader``; translated to ContractError."""

    def __init__(self, key: object, line: int) -> None:
        self.key = key
        self.line = line
        super().__init__(str(key))


if yaml is not None:  # pragma: no branch - PyYAML is a hard dependency

    # Prefer the libyaml-backed C loader when it is available. Measurements on
    # this machine on a 20,000-item review queue: 21.5 s with the pure-Python
    # ``SafeLoader`` versus 5.2 s with ``CSafeLoader`` (4.1x), for byte-identical
    # parsed output. ``CSafeLoader`` is still a *safe* loader -- it refuses
    # arbitrary object construction -- so the security posture is unchanged.
    _LoaderBase = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

    class _StrictSafeLoader(_LoaderBase):  # type: ignore[misc,valid-type]
        """Loader that refuses a mapping key declared more than once.

        YAML's own resolution rule is "last one wins", so
        ``estimated_minutes: 999`` followed by ``estimated_minutes: 10``
        parses to ``10`` and the 999 disappears without a trace. That is the
        same failure this module's ``_reject_unknown_keys`` exists to stop --
        a value the author actually wrote being silently dropped -- and the
        allowed-key check cannot see it, because by the time the mapping
        reaches Python the duplicate is already gone. Fail closed instead.

        The duplicate scan runs before ``super().construct_mapping`` and adds
        one pass over the key nodes; the C loader still wins by several times
        on documents of realistic size.
        """

        def construct_mapping(self, node, deep: bool = False):  # type: ignore[override]
            seen: set[Any] = set()
            merge_key = object()
            for key_node, _ in node.value:
                # SafeLoader expands a single merge key below. Count it as a declared key
                # without constructing it, since its tag has no direct constructor.
                if key_node.tag == "tag:yaml.org,2002:merge":
                    key = merge_key
                else:
                    key = self.construct_object(key_node, deep=deep)
                try:
                    duplicate = key in seen
                except TypeError:  # unhashable key; PyYAML rejects it below
                    continue
                if duplicate:
                    display_key = "<<" if key is merge_key else key
                    raise _DuplicateKeyError(display_key, key_node.start_mark.line + 1)
                seen.add(key)
            return super().construct_mapping(node, deep=deep)


def load_yaml_text(text: str, *, source: str = "<yaml>") -> Any:
    """Parse strict YAML text while rejecting duplicate mapping keys."""
    if yaml is None:  # pragma: no cover
        raise ContractError("PyYAML is required to read contract files", source)
    try:
        return yaml.load(text, Loader=_StrictSafeLoader)
    except _DuplicateKeyError as exc:
        raise ContractError(
            f"duplicate field {exc.key!r} (line {exc.line}); YAML would silently keep "
            "only the last one",
            source,
        ) from exc
    except yaml.YAMLError as exc:  # pragma: no cover - depends on input
        raise ContractError(f"invalid YAML: {exc}", source) from exc


def _read_yaml_file(path: Path) -> Any:
    if not path.is_file():
        raise ContractError(f"file does not exist: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read YAML: {exc}", path.as_posix()) from exc
    return load_yaml_text(text, source=path.as_posix())


# --------------------------------------------------------------------------
# exam configuration contract
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectBudget:
    """One subject's share of the daily budget."""

    subject_id: str
    display_name: str
    weight: float
    active: bool
    min_daily_minutes: int = 0


@dataclass(frozen=True)
class ReviewPolicy:
    """User-selected review algorithm and unchecked self-rating policy."""

    self_rating_mode: str = "strict"
    algorithm: str = "ladder"


@dataclass(frozen=True)
class KaoyanConfig:
    """The exam configuration contract.

    ``default_daily_minutes`` is the fallback when no daily availability is
    entered. M26 ``resolve_daily_minutes`` determines each day's minutes.
    The subject weights are shares of this fallback; active weights sum to 1.
    """

    schema_version: int
    project_id: str
    default_daily_minutes: int
    review_reserve_ratio: float
    hard_max_ratio: float
    subjects: tuple[SubjectBudget, ...]
    review_policy: ReviewPolicy = ReviewPolicy()

    # -- derived views ----------------------------------------------------

    def active_subjects(self) -> tuple[SubjectBudget, ...]:
        return tuple(s for s in self.subjects if s.active)

    def subject(self, subject_id: str) -> SubjectBudget:
        for candidate in self.subjects:
            if candidate.subject_id == subject_id:
                return candidate
        raise ContractError(f"unknown subject_id {subject_id!r}", "subjects")

    def weight_of(self, subject_id: str) -> float:
        return self.subject(subject_id).weight

    def review_target_minutes(self) -> int:
        """Soft quota for review inside one day.

        Computed with exact rational arithmetic. ``int(total * ratio)`` in
        binary floating point raises ``OverflowError`` once ``total`` exceeds
        roughly ``1e308``, which would escape as an uncaught traceback instead
        of the documented clean exit codes. The contract deliberately sets no
        upper bound on ``default_daily_minutes``, so the arithmetic must stay
        exact for every value the contract accepts.
        """
        return scale_minutes(self.default_daily_minutes, self.review_reserve_ratio)

    def review_hard_cap_minutes(self) -> int:
        """Absolute ceiling for review inside one day. See above for why this
        uses exact rational arithmetic rather than float multiplication."""
        return scale_minutes(self.default_daily_minutes, self.hard_max_ratio)


def scale_minutes(total_minutes: int, ratio: float) -> int:
    """Floor of ``total_minutes * ratio`` as exact rational arithmetic.

    ``Fraction(str(ratio))`` reinterprets the validated float as the shortest
    decimal that round-trips to it, which is how a config author writes
    ``0.45`` in YAML. This is the frozen reading of the contract's
    ``floor(total x ratio)``.

    Two consequences are deliberate and tested, so do not "simplify" this back
    to ``int(total_minutes * ratio)``:

    1. Binary float multiplication raises ``OverflowError`` once ``total``
       passes roughly 1e308, and the contract sets no upper bound on
       ``default_daily_minutes``. Exact arithmetic keeps every accepted config
       on the documented clean exit paths.
    2. The two are *not* equivalent for ratios whose decimal form does not
       terminate. At ``total=53, ratio=1/53`` the float product returns 1
       purely because the double multiplication rounds up to exactly 1.0,
       while both exact readings (the decimal as written, and the binary value
       actually stored) floor to 0.

    The two shipped ratios (``0.45``, ``0.60``) agree with ``int(total *
    ratio)`` over the measured range ``total = 1..200000`` -- zero divergences,
    exhaustively checked. That is a bounded, verified statement and not a
    general guarantee: both ratios already differ by one minute at
    ``total = 9007199254740973`` (``0.45`` -> exact 4053239664633437 vs float
    4053239664633438; ``0.60`` -> exact 5404319552844583 vs float
    5404319552844584), and past roughly ``1e308`` the float product raises
    ``OverflowError`` while this function keeps returning an exact integer.
    Where the two differ, this function is right and the float product is the
    rounding artifact.

    The value is exact for any Python integer budget; that is an arithmetic
    guarantee, not a promise about time or memory for absurd inputs.
    """
    return (total_minutes * Fraction(str(ratio))) // 1


def _load_subject(raw: Any, index: int) -> SubjectBudget:
    path = f"subjects[{index}]"
    node = _require_mapping(raw, path)
    _reject_unknown_keys(node, SUBJECT_KEYS, path)

    subject_id = _require_str(node.get("subject_id"), f"{path}.subject_id")
    if not all(ch.isalnum() or ch in "-_" for ch in subject_id):
        raise ContractError(
            "subject_id must contain only letters, digits, '-' or '_'", f"{path}.subject_id"
        )
    display_name = _require_text(node.get("display_name"), f"{path}.display_name")
    weight = _require_float(node.get("weight"), f"{path}.weight", minimum=0.0, maximum=1.0)
    active = _require_bool(node.get("active"), f"{path}.active")

    min_daily_minutes = _require_int(
        node.get("min_daily_minutes", 0), f"{path}.min_daily_minutes", minimum=0
    )

    if active and weight <= 0.0:
        raise ContractError("an active subject must have a positive weight", f"{path}.weight")
    if not active and weight != 0.0:
        raise ContractError("an inactive subject must have weight 0", f"{path}.weight")
    if not active and min_daily_minutes != 0:
        # allocate_new_content() only iterates active subjects, so a floor
        # declared here would never be honoured; catch the contradiction
        # instead of silently ignoring the declared value.
        raise ContractError(
            "an inactive subject must have min_daily_minutes 0", f"{path}.min_daily_minutes"
        )

    return SubjectBudget(
        subject_id=subject_id,
        display_name=display_name,
        weight=weight,
        active=active,
        min_daily_minutes=min_daily_minutes,
    )


def _config_root(raw: Any, source: str) -> Mapping[str, Any]:
    root = _require_mapping(raw, source)
    if "total_daily_minutes" in root:
        raise ContractError(
            "total_daily_minutes 已改名为 default_daily_minutes，请在配置文件里改名",
            "total_daily_minutes",
        )
    _reject_unknown_keys(root, CONFIG_ROOT_KEYS, "")
    return root


def _config_schema_version(root: Mapping[str, Any]) -> int:
    schema_version = _require_int(root.get("schema_version"), "schema_version", minimum=1)
    if schema_version != 1:
        raise ContractError(f"unsupported schema_version {schema_version}", "schema_version")
    return schema_version


def _config_review_policy(root: Mapping[str, Any]) -> ReviewPolicy:
    policy_node = _require_mapping(root.get("review_policy", {}), "review_policy")
    _reject_unknown_keys(
        policy_node, frozenset({"self_rating_mode", "algorithm"}), "review_policy"
    )
    self_rating_mode = policy_node.get("self_rating_mode", "strict")
    if not isinstance(self_rating_mode, str) or self_rating_mode not in {"strict", "lenient"}:
        raise ContractError(
            "self_rating_mode must be strict or lenient", "review_policy.self_rating_mode"
        )
    algorithm = policy_node.get("algorithm", "ladder")
    if not isinstance(algorithm, str) or algorithm not in {"ladder", "fsrs"}:
        raise ContractError(
            "algorithm must be ladder or fsrs", "review_policy.algorithm"
        )
    return ReviewPolicy(self_rating_mode, algorithm)


def _config_project_and_budget(
    root: Mapping[str, Any],
) -> tuple[str, int, float, float]:
    project_id = _require_str(root.get("project_id"), "project_id")
    default_daily_minutes = _require_int(
        root.get("default_daily_minutes"), "default_daily_minutes", minimum=1
    )
    # Ratio bounds are semantic constraints, so weight tolerance must not leak here.
    review_reserve_ratio = _require_float(
        root.get("review_reserve_ratio"),
        "review_reserve_ratio",
        minimum=0.0,
        maximum=1.0,
        tolerance=0.0,
    )
    hard_max_ratio = _require_float(
        root.get("hard_max_ratio"),
        "hard_max_ratio",
        minimum=0.0,
        maximum=1.0,
        tolerance=0.0,
    )
    if hard_max_ratio < review_reserve_ratio:
        raise ContractError(
            f"hard_max_ratio ({hard_max_ratio}) must be >= review_reserve_ratio "
            f"({review_reserve_ratio}); otherwise the soft quota is unreachable",
            "hard_max_ratio",
        )
    if hard_max_ratio <= 0.0:
        raise ContractError("hard_max_ratio must be positive", "hard_max_ratio")
    return project_id, default_daily_minutes, review_reserve_ratio, hard_max_ratio


def _config_subjects(root: Mapping[str, Any]) -> tuple[SubjectBudget, ...]:
    raw_subjects = root.get("subjects")
    if not isinstance(raw_subjects, Sequence) or isinstance(raw_subjects, (str, bytes)):
        raise ContractError("expected a list of subjects", "subjects")
    if not raw_subjects:
        raise ContractError("at least one subject is required", "subjects")
    return tuple(_load_subject(item, index) for index, item in enumerate(raw_subjects))


def _check_unique_subject_ids(subjects: Sequence[SubjectBudget]) -> None:
    seen: set[str] = set()
    for index, subject in enumerate(subjects):
        if subject.subject_id in seen:
            raise ContractError(
                f"duplicate subject_id {subject.subject_id!r}", f"subjects[{index}].subject_id"
            )
        seen.add(subject.subject_id)


def _active_subjects(subjects: Sequence[SubjectBudget]) -> tuple[SubjectBudget, ...]:
    active = tuple(subject for subject in subjects if subject.active)
    if not active:
        raise ContractError("at least one active subject is required", "subjects")
    return active


def _check_active_weight_total(active: Sequence[SubjectBudget]) -> None:
    total_weight = sum(subject.weight for subject in active)
    if abs(total_weight - 1.0) > WEIGHT_TOLERANCE:
        raise ContractError(
            f"active subject weights must sum to 1.0 (got {total_weight!r})", "subjects"
        )


def _check_subject_minimums(
    subjects: Sequence[SubjectBudget], default_daily_minutes: int
) -> None:
    for index, subject in enumerate(subjects):
        if subject.min_daily_minutes > default_daily_minutes:
            raise ContractError(
                f"min_daily_minutes ({subject.min_daily_minutes}) exceeds "
                f"default_daily_minutes ({default_daily_minutes})",
                f"subjects[{index}].min_daily_minutes",
            )


def _check_floor_room(
    active: Sequence[SubjectBudget], default_daily_minutes: int, hard_max_ratio: float
) -> None:
    # Policy choice from M3: floors and the review hard cap share one budget.
    review_hard_cap = scale_minutes(default_daily_minutes, hard_max_ratio)
    floor_total = sum(subject.min_daily_minutes for subject in active)
    if floor_total > default_daily_minutes - review_hard_cap:
        raise ContractError(
            f"sum of active min_daily_minutes ({floor_total}) leaves less than "
            f"the review hard cap ({review_hard_cap}) of new-content room out of "
            f"{default_daily_minutes} total minutes; lower the floors or hard_max_ratio",
            "subjects",
        )


def validate_config(raw: Any, *, source: str = "<mapping>") -> KaoyanConfig:
    """Validate a parsed config mapping and return the typed contract."""
    root = _config_root(raw, source)
    schema_version = _config_schema_version(root)
    review_policy = _config_review_policy(root)
    project_id, default_daily_minutes, review_reserve_ratio, hard_max_ratio = (
        _config_project_and_budget(root)
    )
    subjects = _config_subjects(root)
    _check_unique_subject_ids(subjects)
    active = _active_subjects(subjects)
    _check_active_weight_total(active)
    _check_subject_minimums(subjects, default_daily_minutes)
    _check_floor_room(active, default_daily_minutes, hard_max_ratio)
    return KaoyanConfig(
        schema_version=schema_version,
        project_id=project_id,
        default_daily_minutes=default_daily_minutes,
        review_reserve_ratio=review_reserve_ratio,
        hard_max_ratio=hard_max_ratio,
        subjects=subjects,
        review_policy=review_policy,
    )


def load_config(path: str | Path) -> KaoyanConfig:
    """Read and validate a config file from disk."""
    resolved = Path(path)
    return validate_config(_read_yaml_file(resolved), source=resolved.as_posix())


def load_config_mapping(mapping: Mapping[str, Any]) -> KaoyanConfig:
    """Validate an already-parsed config mapping (used by tests and callers)."""
    return validate_config(mapping)


def config_to_mapping(config: KaoyanConfig) -> dict[str, Any]:
    """Return the config as a plain mapping for M19 / M28 input packages.

    ``review_policy.algorithm`` is written only when it is not the default ``ladder``:
    input packages of configs that omit the key must keep their bytes and hashes
    (``contracts/review_progress.md`` FSRS section, AGENTS.md known defect 7).
    """
    mapping = asdict(config)
    if config.review_policy.algorithm == "ladder":
        del mapping["review_policy"]["algorithm"]
    return mapping


# --------------------------------------------------------------------------
# review item contract
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewSchedule:
    """Spaced-repetition state for one review item.

    ``interval_days`` is the *current* interval actually in force. It is never
    written by an AI and never derived from self-report alone.
    """

    mode: str
    phase: int
    interval_days: int
    ease_factor: float
    repetitions: int
    lapses: int
    stability: float | None = None
    difficulty: float | None = None
    fsrs_reviewed_on: date | None = None


@dataclass(frozen=True)
class ReviewItem:
    review_id: str
    revision: int
    subject_id: str
    knowledge_point_id: str
    title: str
    granularity: str
    state: str
    estimated_minutes: int
    introduced_on: date
    due_date: date
    last_reviewed_on: date | None
    schedule: ReviewSchedule
    defer_count: int
    last_quality: int | None
    last_self_rating: str | None = None

    def overdue_days(self, today: date) -> int:
        """Days past due. Zero or negative when not yet past due."""
        return (today - self.due_date).days

    def is_due(self, today: date) -> bool:
        return self.state == "queued" and self.due_date <= today

    def with_deferral(self) -> "ReviewItem":
        """Return a copy with ``defer_count`` incremented and due_date intact.

        Deferral deliberately does not rewrite ``due_date``: the growing
        ``overdue_days`` is what raises priority later, so no hidden state has
        to be written back and no audit entry is needed.
        """
        return ReviewItem(
            review_id=self.review_id,
            revision=self.revision,
            subject_id=self.subject_id,
            knowledge_point_id=self.knowledge_point_id,
            title=self.title,
            granularity=self.granularity,
            state=self.state,
            estimated_minutes=self.estimated_minutes,
            introduced_on=self.introduced_on,
            due_date=self.due_date,
            last_reviewed_on=self.last_reviewed_on,
            schedule=self.schedule,
            defer_count=self.defer_count + 1,
            last_quality=self.last_quality,
            last_self_rating=self.last_self_rating,
        )


def _load_schedule(raw: Any, path: str) -> ReviewSchedule:
    node = _require_mapping(raw, path)
    _reject_unknown_keys(node, SCHEDULE_KEYS, path)

    mode = _require_str(node.get("mode"), f"{path}.mode")
    if mode not in VALID_SCHEDULE_MODES:
        raise ContractError(
            f"mode must be one of {', '.join(VALID_SCHEDULE_MODES)}, got {mode!r}", f"{path}.mode"
        )

    phase = _require_int(node.get("phase"), f"{path}.phase", minimum=0, maximum=5)
    interval_days = _require_int(
        node.get("interval_days"), f"{path}.interval_days", minimum=1, maximum=180
    )
    ease_factor = _require_float(
        node.get("ease_factor"), f"{path}.ease_factor", minimum=1.3, maximum=3.0
    )
    repetitions = _require_int(node.get("repetitions"), f"{path}.repetitions", minimum=0)
    lapses = _require_int(node.get("lapses"), f"{path}.lapses", minimum=0)
    fsrs_fields = ("stability", "difficulty", "fsrs_reviewed_on")
    present = tuple(field in node for field in fsrs_fields)
    if mode == "fsrs":
        stability = _require_float(
            node.get("stability"), f"{path}.stability", minimum=0.0, tolerance=0.0
        )
        if stability == 0:
            raise ContractError("must be > 0", f"{path}.stability")
        difficulty = _require_float(
            node.get("difficulty"), f"{path}.difficulty", minimum=1.0, maximum=10.0,
            tolerance=0.0,
        )
        fsrs_reviewed_on = _parse_fsrs_date(
            node.get("fsrs_reviewed_on"), f"{path}.fsrs_reviewed_on"
        )
    else:
        if any(present):
            field = fsrs_fields[present.index(True)]
            raise ContractError("FSRS fields require mode fsrs", f"{path}.{field}")
        stability = difficulty = fsrs_reviewed_on = None

    if mode == "fixed_bootstrap" and phase >= 5:
        raise ContractError(
            "fixed_bootstrap must have phase <= 4; phase 5 means the item is in sm2_lite",
            f"{path}.phase",
        )
    if mode == "sm2_lite" and phase < 5:
        raise ContractError("sm2_lite requires phase >= 5", f"{path}.phase")
    if mode == "fsrs" and phase != 5:
        raise ContractError("fsrs requires phase 5", f"{path}.phase")

    return ReviewSchedule(
        mode=mode,
        phase=phase,
        interval_days=interval_days,
        ease_factor=ease_factor,
        repetitions=repetitions,
        lapses=lapses,
        stability=stability,
        difficulty=difficulty,
        fsrs_reviewed_on=fsrs_reviewed_on,
    )


def _parse_fsrs_date(value: Any, path: str) -> date:
    if type(value) is date:
        return value
    if not isinstance(value, str) or isinstance(value, datetime):
        raise ContractError("expected an ISO date (YYYY-MM-DD)", path)
    parsed = _parse_date(value, path)
    assert parsed is not None
    if value.strip() != parsed.isoformat():
        raise ContractError("expected an ISO date (YYYY-MM-DD)", path)
    return parsed


def _review_item_label(index: int | None, source: str) -> str:
    return f"items[{index}]" if index is not None else source


def _review_item_identity_and_title(
    node: Mapping[str, Any], label: str
) -> tuple[str, int, str, str, str]:
    review_id = _require_str(node.get("review_id"), f"{label}.review_id")
    revision = _require_int(node.get("revision"), f"{label}.revision", minimum=1)
    subject_id = _require_str(node.get("subject_id"), f"{label}.subject_id")
    knowledge_point_id = _require_str(
        node.get("knowledge_point_id"), f"{label}.knowledge_point_id"
    )
    title = _require_str(node.get("title"), f"{label}.title")
    return review_id, revision, subject_id, knowledge_point_id, title


def _review_item_categories(node: Mapping[str, Any], label: str) -> tuple[str, str]:
    granularity = _require_str(node.get("granularity"), f"{label}.granularity")
    if granularity not in VALID_GRANULARITIES:
        raise ContractError(
            f"granularity must be one of {', '.join(VALID_GRANULARITIES)}, got {granularity!r}",
            f"{label}.granularity",
        )
    state = _require_str(node.get("state"), f"{label}.state")
    if state not in VALID_REVIEW_STATES:
        raise ContractError(
            f"state must be one of {', '.join(VALID_REVIEW_STATES)}, got {state!r}",
            f"{label}.state",
        )
    return granularity, state


def _review_item_estimated_minutes(node: Mapping[str, Any], label: str) -> int:
    estimated_minutes = _require_int(
        node.get("estimated_minutes"), f"{label}.estimated_minutes", minimum=1
    )
    if estimated_minutes > MAX_SINGLE_PASS_MINUTES:
        raise ContractError(
            f"estimated_minutes ({estimated_minutes}) exceeds the {MAX_SINGLE_PASS_MINUTES} minute "
            "single-pass cap; split the item before importing it",
            f"{label}.estimated_minutes",
        )
    return estimated_minutes


def _review_item_dates(
    node: Mapping[str, Any], label: str
) -> tuple[date, date, date | None]:
    introduced_on = _parse_date(node.get("introduced_on"), f"{label}.introduced_on")
    due_date = _parse_date(node.get("due_date"), f"{label}.due_date")
    last_reviewed_on = _parse_date(
        node.get("last_reviewed_on"), f"{label}.last_reviewed_on", optional=True
    )
    assert introduced_on is not None and due_date is not None
    if due_date < introduced_on:
        raise ContractError(
            f"due_date ({due_date}) must not precede introduced_on ({introduced_on})",
            f"{label}.due_date",
        )
    if last_reviewed_on is not None and last_reviewed_on < introduced_on:
        raise ContractError(
            f"last_reviewed_on ({last_reviewed_on}) must not precede "
            f"introduced_on ({introduced_on})",
            f"{label}.last_reviewed_on",
        )
    return introduced_on, due_date, last_reviewed_on


def _review_item_feedback(
    node: Mapping[str, Any], label: str
) -> tuple[int | None, str | None]:
    last_quality = node.get("last_quality")
    if last_quality is not None:
        last_quality = _require_int(
            last_quality, f"{label}.last_quality", minimum=0, maximum=5
        )
    last_self_rating = node.get("self_rating")
    if last_self_rating is not None:
        last_self_rating = _require_str(last_self_rating, f"{label}.self_rating")
        if last_self_rating not in VALID_SELF_RATINGS:
            raise ContractError(
                f"self_rating must be one of {', '.join(VALID_SELF_RATINGS)}, "
                f"got {last_self_rating!r}",
                f"{label}.self_rating",
            )
    return last_quality, last_self_rating


def _check_vocabulary_minutes(granularity: str, estimated_minutes: int, label: str) -> None:
    if granularity == "vocabulary_batch" and estimated_minutes > 5:
        raise ContractError(
            "vocabulary_batch items are batched flashcards and must cost <= 5 minutes per pass",
            f"{label}.estimated_minutes",
        )


def validate_review_item(
    raw: Any, *, index: int | None = None, source: str = "<item>"
) -> ReviewItem:
    label = _review_item_label(index, source)
    node = _require_mapping(raw, label)
    _reject_unknown_keys(node, REVIEW_ITEM_KEYS, label)
    review_id, revision, subject_id, knowledge_point_id, title = _review_item_identity_and_title(
        node, label
    )
    granularity, state = _review_item_categories(node, label)
    estimated_minutes = _review_item_estimated_minutes(node, label)
    introduced_on, due_date, last_reviewed_on = _review_item_dates(node, label)
    schedule = _load_schedule(node.get("schedule"), f"{label}.schedule")
    defer_count = _require_int(node.get("defer_count"), f"{label}.defer_count", minimum=0)
    last_quality, last_self_rating = _review_item_feedback(node, label)
    _check_vocabulary_minutes(granularity, estimated_minutes, label)
    return ReviewItem(
        review_id=review_id,
        revision=revision,
        subject_id=subject_id,
        knowledge_point_id=knowledge_point_id,
        title=title,
        granularity=granularity,
        state=state,
        estimated_minutes=estimated_minutes,
        introduced_on=introduced_on,
        due_date=due_date,
        last_reviewed_on=last_reviewed_on,
        schedule=schedule,
        defer_count=defer_count,
        last_quality=last_quality,
        last_self_rating=last_self_rating,
    )


def load_review_items(path: str | Path) -> tuple[ReviewItem, ...]:
    """Read and validate a review item list from disk.

    Accepts either a bare YAML list or a mapping with ``schema_version`` and
    ``items`` keys. When a root mapping is present its ``schema_version`` is
    mandatory and checked against ``REVIEWS_SCHEMA_VERSION`` -- it is not
    just parsed and then ignored.
    """
    resolved = Path(path)
    raw = _read_yaml_file(resolved)
    if isinstance(raw, Mapping):
        source = resolved.as_posix()
        _reject_unknown_keys(raw, REVIEWS_ROOT_KEYS, source)
        schema_version = _require_int(
            raw.get("schema_version"), f"{source}.schema_version", minimum=1
        )
        if schema_version != REVIEWS_SCHEMA_VERSION:
            raise ContractError(
                f"unsupported schema_version {schema_version}", f"{source}.schema_version"
            )
        raw = raw.get("items")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ContractError("expected a list of review items", resolved.as_posix())

    items = tuple(
        validate_review_item(item, index=index, source=resolved.as_posix())
        for index, item in enumerate(raw)
    )

    seen: set[str] = set()
    for index, item in enumerate(items):
        if item.review_id in seen:
            raise ContractError(
                f"duplicate review_id {item.review_id!r}", f"items[{index}].review_id"
            )
        seen.add(item.review_id)

    return items


def validate_review_items(
    raw_items: Iterable[Any], *, source: str = "<items>"
) -> tuple[ReviewItem, ...]:
    """Validate an in-memory sequence of review item mappings."""
    items = tuple(
        validate_review_item(item, index=index, source=source)
        for index, item in enumerate(raw_items)
    )
    seen: set[str] = set()
    for index, item in enumerate(items):
        if item.review_id in seen:
            raise ContractError(
                f"duplicate review_id {item.review_id!r}", f"items[{index}].review_id"
            )
        seen.add(item.review_id)
    return items


def validate_items_against_config(config: KaoyanConfig, items: Iterable[ReviewItem]) -> None:
    """Reject review items whose ``subject_id`` is missing or inactive.

    Each file validates in isolation (config on its own, items on their own),
    so nothing else catches a typo'd or retired ``subject_id``. Without this
    check such an item would silently be scheduled with a neutral (zero)
    subject-deficit ratio instead of being caught as a contract violation.
    ``select_daily_reviews`` also calls this so the guarantee holds even for
    callers that skip preflight's explicit call.
    """
    known = {subject.subject_id for subject in config.subjects}
    active = {subject.subject_id for subject in config.subjects if subject.active}
    for index, item in enumerate(items):
        if item.subject_id not in known:
            raise ContractError(
                f"subject_id {item.subject_id!r} is not declared in config.subjects",
                f"items[{index}].subject_id",
            )
        if item.subject_id not in active:
            raise ContractError(
                f"subject_id {item.subject_id!r} refers to an inactive subject",
                f"items[{index}].subject_id",
            )
