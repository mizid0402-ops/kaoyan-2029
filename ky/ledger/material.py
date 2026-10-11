"""M2 material ledger from ``contracts/ledger.md``.

Public interfaces: :func:`load_ledger`, :func:`validate_ledger`, and
:func:`integrity_report`.

Material ledger: provenance, rights, and integrity for every source.

The ledger is the *only* place a source's identity and legal standing is
recorded. Nothing downstream may invent a source, and no structured claim may
be derived from a material that is not present locally and explicitly permits
structuring (see ``may_be_structured``).

Design rules:

1. **Fail closed on rights.** An unknown licence is not permission. A material
   whose rights are unclear can be registered and cited as a link, but it
   cannot authorise a derived claim and it cannot be displayed.
2. **Two storage modes are not equivalent.** A ``local_file`` material carries
   bytes and a SHA-256 that can be re-verified. A ``remote_reference`` material
   carries no local bytes, so it can never back an evidence hash. Treating
   them as the same thing is exactly how a broken citation reaches a plan.
3. **The audit trail is append-only.** Registrations, right changes and
   withdrawals are recorded as events; the current view is derived from them.
   Nothing is silently overwritten, because a withdrawn material must stay
   explainable.
4. Unknown keys are rejected with a precise path, matching ``ky.models`` and
   ``ky.knowledge``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # pragma: no cover - exercised only when PyYAML is absent
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from ky.models import ContractError, load_yaml_text

MATERIAL_SCHEMA_VERSION = 1

# What the material actually is. Kept deliberately narrow: these are the kinds
# the kaoyan workflow needs, not a general document taxonomy.
VALID_MATERIAL_KINDS = frozenset(
    {
        "official_syllabus",  # 教育部教育考试院发布的考试大纲
        "outline_structure",  # 教材/大纲的章节结构（可合法引用的目录级信息）
        "official_exam_notice",  # 考试公告、时间安排等元信息
        "textbook",  # 教材
        "past_exam_paper",  # 真题（用户持有或授权取得）
        "reference_notes",  # 参考资料、讲义
        "ai_generated",  # AI 生成的练习/草稿
    }
)

VALID_ACQUISITION = frozenset(
    {"public_download", "user_provided", "licensed", "purchased", "generated", "unknown"}
)

VALID_RIGHTS_STATUS = frozenset(
    {
        "public_domain",  # 公有领域
        "official_public",  # 官方公开发布（例如已出版的考试大纲）
        "licensed",  # 已获授权
        "personal_use",  # 个人合法持有，仅自用
        "unknown",  # 权利状态不明 —— 不等于可用
        "restricted",  # 明确受限
        # Exam material moves through explicit phases. Collapsing them into one
        # "exam paper" status is what let the project previously assume the
        # official papers carry no answers; the reconnaissance found they do.
        "state_secret_exam_period",  # 命题/运输/保管/考试期间属国家秘密 —— 不得持有
        "officially_published",  # 考试结束后官方出版公开（真题与参考答案在此列）
        "scoring_rubric_restricted",  # 评分细则：考后亦不得发表
    }
)

# Statuses that may never authorise anything, regardless of the permission
# flags an author writes. These are legal facts, not preferences, so they are
# enforced rather than trusted.
FORBIDDEN_RIGHTS_STATUS = frozenset(
    {"state_secret_exam_period", "scoring_rubric_restricted"}
)

VALID_STORAGE_MODES = frozenset({"local_file", "remote_reference"})

# How much the *bytes we hold* can be trusted, which is a different question
# from what we are *allowed* to do with them. A file can be perfectly legal to
# hold and still be a sloppy third-hand transcription; conflating the two is
# how a reprint site ends up cited as if it were the ministry.
VALID_SOURCE_TIERS = frozenset(
    {
        "official",  # 教育部 / 教育考试院 / 研招网：可作底层事实源
        "official_publisher",  # 官方组织编写并由人教社等正式出版
        "university",  # 高校官方站点发布的教学/备考资料
        "trusted_reprint",  # 大型机构或可信站点的转载，须交叉验证
        "community_archive",  # 论坛、网盘、个人整理：只能用于查漏与线索
    }
)

# Tiers that may define what the syllabus contains. Anything weaker may inform
# but never decide: "AI 不得根据自己知道的 408 补充考纲节点" applies equally to
# a forum post.
SYLLABUS_AUTHORITATIVE_TIERS = frozenset({"official", "official_publisher", "university"})

VALID_REVIEW_STATUS = frozenset({"unreviewed", "verified", "withdrawn"})

LEDGER_SUBJECT_CATEGORIES = frozenset({"general"})


def _subject_ids_for_validation() -> frozenset[str]:
    from ky.workspace import load_workspace

    return frozenset(load_workspace().subjects) | LEDGER_SUBJECT_CATEGORIES

_MATERIAL_KEYS = {
    "schema_version",
    "resource_id",
    "title",
    "material_kind",
    "subjects",
    "acquisition",
    "rights",
    "storage",
    "provenance",
    "review_index",
    "review_status",
    "notes",
    "history",
}

_RIGHTS_KEYS = {
    "status",
    "licence",
    "licence_url",
    "may_store",
    "may_display",
    "may_redistribute",
    "may_be_structured",
}

_STORAGE_KEYS = {"mode", "path", "sha256", "byte_size", "url", "retrieved_on"}

_PROVENANCE_KEYS = {
    "source_url",
    "source_tier",
    "publisher",
    "published_on",
    "isbn",
    "retrieved_at",
    "retrieved_by",
    "archive_url",
}

_HISTORY_KEYS = {"at", "action", "actor", "detail"}

VALID_HISTORY_ACTIONS = frozenset(
    {"registered", "rights_changed", "path_changed", "verified", "withdrawn", "superseded"}
)


class LedgerError(ValueError):
    """Raised for a structurally or semantically invalid ledger entry."""

    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


# --------------------------------------------------------------------------
# primitives (same shape as ky.models / ky.knowledge so callers see one style)
# --------------------------------------------------------------------------


def _map(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LedgerError(f"expected a mapping, got {type(value).__name__}", path)
    return value


def _unknown(node: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extra = sorted(set(node) - allowed)
    if extra:
        key = extra[0]
        raise LedgerError(f"unknown field {key!r}", f"{path}.{key}" if path else key)


def _str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError("expected a non-empty string", path)
    return value


def _text(value: Any, path: str) -> str:
    """Like ``_str`` but tolerates numeric YAML scalars (e.g. an ISBN)."""
    if isinstance(value, bool):
        raise LedgerError("expected a non-empty string", path)
    if isinstance(value, int):
        return str(value)
    return _str(value, path)


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise LedgerError(f"expected a boolean, got {type(value).__name__}", path)
    return value


def _int(value: Any, path: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedgerError(f"expected an integer, got {type(value).__name__}", path)
    if minimum is not None and value < minimum:
        raise LedgerError(f"must be >= {minimum}, got {value}", path)
    return value


def _enum(value: Any, path: str, allowed: frozenset[str]) -> str:
    text = _str(value, path)
    if text not in allowed:
        raise LedgerError(
            f"must be one of {', '.join(sorted(allowed))}, got {text!r}", path
        )
    return text


def _sha256_text(value: Any, path: str) -> str:
    digest = _str(value, path)
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        raise LedgerError("expected a 64-character SHA-256 hex digest", path)
    return digest.lower()


def _parse_date(value: Any, path: str, *, optional: bool = False) -> date | None:
    if value is None:
        if optional:
            return None
        raise LedgerError("expected an ISO date (YYYY-MM-DD)", path)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise LedgerError(f"expected an ISO date (YYYY-MM-DD), got {value!r}", path) from exc
    raise LedgerError(f"expected an ISO date (YYYY-MM-DD), got {type(value).__name__}", path)


def sha256_bytes(data: bytes) -> str:
    """Hash helper so callers never hand-roll the digest."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash a file's bytes without loading it all into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# rights
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Rights:
    """What the project is allowed to do with this material.

    ``unknown`` is the default posture and it permits nothing beyond
    registering a link. Every permission is an explicit opt-in.
    """

    status: str
    licence: str | None
    licence_url: str | None
    may_store: bool
    may_display: bool
    may_redistribute: bool
    may_be_structured: bool

    def is_clear(self) -> bool:
        """True when the rights position is known, not merely assumed."""
        return self.status != "unknown"

    def permits_evidence(self) -> bool:
        """Whether a claim may cite this material as evidence.

        Requires both a clear rights position and explicit permission to derive
        structure. This is the gate ``ky.knowledge`` provenance relies on.
        """
        return self.is_clear() and self.may_be_structured


def _load_rights(raw: Any, path: str, *, storage_mode: str) -> Rights:
    node = _map(raw, path)
    _unknown(node, _RIGHTS_KEYS, path)

    status = _enum(node.get("status"), f"{path}.status", VALID_RIGHTS_STATUS)
    licence = node.get("licence")
    if licence is not None:
        licence = _text(licence, f"{path}.licence")
    licence_url = node.get("licence_url")
    if licence_url is not None:
        licence_url = _str(licence_url, f"{path}.licence_url")

    may_store = _bool(node.get("may_store"), f"{path}.may_store")
    may_display = _bool(node.get("may_display"), f"{path}.may_display")
    may_redistribute = _bool(node.get("may_redistribute"), f"{path}.may_redistribute")
    may_be_structured = _bool(node.get("may_be_structured"), f"{path}.may_be_structured")

    _validate_rights_permissions(
        status, may_store, may_display, may_redistribute, may_be_structured,
        storage_mode=storage_mode, path=path,
    )

    return Rights(
        status=status,
        licence=licence,
        licence_url=licence_url,
        may_store=may_store,
        may_display=may_display,
        may_redistribute=may_redistribute,
        may_be_structured=may_be_structured,
    )


def _validate_rights_permissions(
    status: str,
    may_store: bool,
    may_display: bool,
    may_redistribute: bool,
    may_be_structured: bool,
    *,
    storage_mode: str,
    path: str,
) -> None:

    # Contradiction guards. These are the ones that would otherwise let an
    # unclear right quietly turn into a permission.
    if status in FORBIDDEN_RIGHTS_STATUS:
        # A legal prohibition is not overridable by a flag in a config file.
        if may_store or may_display or may_redistribute or may_be_structured:
            raise LedgerError(
                f"rights.status {status!r} may not permit store/display/redistribute/structuring; "
                "exam-period material must not be held at all, and scoring rubrics may not be "
                "published even after the exam",
                f"{path}.status",
            )
    if status == "unknown" and (may_display or may_redistribute):
        raise LedgerError(
            "rights.status 'unknown' cannot permit display or redistribution; "
            "resolve the licence or set status explicitly",
            f"{path}.status",
        )
    if status == "restricted" and (may_display or may_redistribute):
        raise LedgerError(
            "rights.status 'restricted' cannot permit display or redistribution",
            f"{path}.status",
        )
    if may_redistribute and not may_display:
        raise LedgerError(
            "may_redistribute implies may_display; set may_display as well",
            f"{path}.may_redistribute",
        )
    if may_display and not may_store:
        raise LedgerError(
            "may_display requires may_store: the project has no server that could "
            "display something it is not allowed to keep",
            f"{path}.may_display",
        )
    if storage_mode == "remote_reference" and may_store:
        raise LedgerError(
            "storage.mode 'remote_reference' holds no local bytes, so may_store must be "
            "false; use local_file when the bytes are kept",
            f"{path}.may_store",
        )
    if may_be_structured and not may_store:
        raise LedgerError(
            "may_be_structured requires may_store: structure can only be derived from "
            "bytes the project actually holds",
            f"{path}.may_be_structured",
        )


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Storage:
    mode: str
    path: str | None
    sha256: str | None
    byte_size: int | None
    url: str | None
    retrieved_on: date | None

    def has_verifiable_bytes(self) -> bool:
        return self.mode == "local_file" and self.sha256 is not None


def _load_storage(raw: Any, path: str) -> Storage:
    node = _map(raw, path)
    _unknown(node, _STORAGE_KEYS, path)

    mode = _enum(node.get("mode"), f"{path}.mode", VALID_STORAGE_MODES)
    storage_path = node.get("path")
    url = node.get("url")
    digest = node.get("sha256")
    byte_size = node.get("byte_size")
    retrieved_on = _parse_date(node.get("retrieved_on"), f"{path}.retrieved_on", optional=True)

    if mode == "local_file":
        storage_path = _str(storage_path, f"{path}.path")
        digest = _sha256_text(digest, f"{path}.sha256")
        byte_size = _int(byte_size, f"{path}.byte_size", minimum=0)
        if url is not None:
            url = _str(url, f"{path}.url")
    else:  # remote_reference
        url = _str(url, f"{path}.url")
        if storage_path is not None:
            raise LedgerError(
                "a remote_reference must not declare a local path", f"{path}.path"
            )
        if digest is not None:
            raise LedgerError(
                "a remote_reference cannot carry a verified sha256; download it and "
                "register as local_file if the hash matters",
                f"{path}.sha256",
            )
        if byte_size is not None:
            raise LedgerError(
                "a remote_reference has no local byte_size", f"{path}.byte_size"
            )

    return Storage(
        mode=mode,
        path=storage_path,
        sha256=digest,
        byte_size=byte_size,
        url=url,
        retrieved_on=retrieved_on,
    )


# --------------------------------------------------------------------------
# material
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    source_url: str | None
    source_tier: str
    publisher: str | None
    published_on: date | None
    isbn: str | None
    retrieved_at: datetime | None
    retrieved_by: str | None
    archive_url: str | None = None

    def may_define_syllabus(self) -> bool:
        """Whether this source may decide what the syllabus contains.

        Weaker tiers may supply leads, cross-checks and question text, but a
        claim about exam scope has to rest on an official or university source.
        """
        return self.source_tier in SYLLABUS_AUTHORITATIVE_TIERS


@dataclass(frozen=True)
class HistoryEvent:
    at: datetime | None
    action: str
    actor: str
    detail: str | None


@dataclass(frozen=True)
class Material:
    schema_version: int
    resource_id: str
    title: str
    material_kind: str
    subjects: tuple[str, ...]
    acquisition: str
    rights: Rights
    storage: Storage
    provenance: Provenance
    review_index: bool
    review_status: str
    notes: str | None
    history: tuple[HistoryEvent, ...] = field(default=())

    def may_be_structured(self) -> bool:
        """Whether claims may be derived from this material right now."""
        return (
            self.review_status != "withdrawn"
            and self.rights.permits_evidence()
            and self.storage.has_verifiable_bytes()
        )

    def can_back_evidence(self) -> bool:
        """Whether this material can be cited with a real ``path + sha256``."""
        return self.review_status != "withdrawn" and self.storage.has_verifiable_bytes()

    def verify_bytes(self, root: str | Path | None = None) -> bool:
        """Re-hash the stored file and compare against the recorded digest.

        Returns False rather than raising so callers can report per-material
        integrity the way the rest of the project reports per-file integrity.
        """
        if self.storage.mode != "local_file" or self.storage.path is None:
            return False
        candidate = Path(self.storage.path)
        if not candidate.is_absolute() and root is not None:
            candidate = Path(root) / candidate
        if not candidate.is_file():
            return False
        return sha256_file(candidate) == self.storage.sha256


def _load_history(raw: Any, path: str) -> tuple[HistoryEvent, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise LedgerError("expected a list", path)
    events: list[HistoryEvent] = []
    for index, entry in enumerate(raw):
        item_path = f"{path}[{index}]"
        node = _map(entry, item_path)
        _unknown(node, _HISTORY_KEYS, item_path)
        action = _enum(node.get("action"), f"{item_path}.action", VALID_HISTORY_ACTIONS)
        actor = _str(node.get("actor"), f"{item_path}.actor")
        at = node.get("at")
        parsed_at: datetime | None = None
        if at is not None:
            if isinstance(at, str):
                try:
                    parsed_at = datetime.fromisoformat(at.strip())
                except ValueError as exc:
                    raise LedgerError(
                        f"expected an ISO-8601 timestamp, got {at!r}", f"{item_path}.at"
                    ) from exc
            elif isinstance(at, datetime):
                parsed_at = at
            else:
                raise LedgerError(
                    f"expected an ISO-8601 timestamp, got {type(at).__name__}", f"{item_path}.at"
                )
        detail = node.get("detail")
        if detail is not None:
            detail = _text(detail, f"{item_path}.detail")
        events.append(HistoryEvent(at=parsed_at, action=action, actor=actor, detail=detail))
    return tuple(events)


def validate_material(
    raw: Any,
    *,
    source: str = "<material>",
    subject_ids: frozenset[str] | None = None,
) -> Material:
    allowed_subjects = (
        subject_ids if subject_ids is not None else _subject_ids_for_validation()
    )
    node = _map(raw, source)
    _unknown(node, _MATERIAL_KEYS, source)

    schema_version = _load_material_schema_version(node, source)

    resource_id = _str(node.get("resource_id"), f"{source}.resource_id")
    title = _str(node.get("title"), f"{source}.title")
    material_kind = _enum(
        node.get("material_kind"), f"{source}.material_kind", VALID_MATERIAL_KINDS,
    )
    acquisition = _enum(node.get("acquisition"), f"{source}.acquisition", VALID_ACQUISITION)

    subjects = _load_material_subjects(node.get("subjects"), allowed_subjects, source)

    storage = _load_storage(node.get("storage"), f"{source}.storage")
    rights = _load_rights(node.get("rights"), f"{source}.rights", storage_mode=storage.mode)
    provenance = _load_material_provenance(node.get("provenance", {}), source)

    notes = node.get("notes")
    if notes is not None:
        notes = _text(notes, f"{source}.notes")

    review_status = _enum(
        node.get("review_status", "unreviewed"),
        f"{source}.review_status", VALID_REVIEW_STATUS,
    )
    review_index = _bool(node.get("review_index", False), f"{source}.review_index")

    _validate_material_origin(provenance, acquisition, storage, source)
    history = _load_history(node.get("history"), f"{source}.history")

    return Material(
        schema_version=schema_version,
        resource_id=resource_id,
        title=title,
        material_kind=material_kind,
        subjects=subjects,
        acquisition=acquisition,
        rights=rights,
        storage=storage,
        provenance=provenance,
        review_index=review_index,
        review_status=review_status,
        notes=notes,
        history=history,
    )


def _load_material_schema_version(node: Mapping[str, Any], source: str) -> int:
    schema_version = _int(
        node.get("schema_version", MATERIAL_SCHEMA_VERSION),
        f"{source}.schema_version", minimum=1,
    )
    if schema_version != MATERIAL_SCHEMA_VERSION:
        raise LedgerError(
            f"unsupported schema_version {schema_version}", f"{source}.schema_version",
        )
    return schema_version


def _load_material_subjects(
    raw_subjects: Any,
    allowed_subjects: frozenset[str],
    source: str,
) -> tuple[str, ...]:
    if (
        not isinstance(raw_subjects, Sequence)
        or isinstance(raw_subjects, (str, bytes))
        or not raw_subjects
    ):
        raise LedgerError("expected a non-empty list of subject ids", f"{source}.subjects")
    subjects: list[str] = []
    for index, entry in enumerate(raw_subjects):
        subject = _str(entry, f"{source}.subjects[{index}]")
        if subject not in allowed_subjects:
            raise LedgerError(
                f"unknown subject id, expected one of {', '.join(sorted(allowed_subjects))}",
                f"{source}.subjects[{index}]",
            )
        subjects.append(subject)
    if len(set(subjects)) != len(subjects):
        raise LedgerError("duplicate subject id", f"{source}.subjects")
    return tuple(subjects)


def _load_material_provenance(raw_prov: Any, source: str) -> Provenance:
    prov_node = _map(raw_prov, f"{source}.provenance")
    _unknown(prov_node, _PROVENANCE_KEYS, f"{source}.provenance")
    # Default to the weakest tier: an unstated trust level is not a high one.
    source_tier = _enum(
        prov_node.get("source_tier", "community_archive"),
        f"{source}.provenance.source_tier",
        VALID_SOURCE_TIERS,
    )
    source_url = prov_node.get("source_url")
    if source_url is not None:
        source_url = _str(source_url, f"{source}.provenance.source_url")
    archive_url = prov_node.get("archive_url")
    if archive_url is not None:
        archive_url = _str(archive_url, f"{source}.provenance.archive_url")
    publisher = prov_node.get("publisher")
    if publisher is not None:
        publisher = _text(publisher, f"{source}.provenance.publisher")
    isbn = prov_node.get("isbn")
    if isbn is not None:
        isbn = _text(isbn, f"{source}.provenance.isbn")
    retrieved_by = prov_node.get("retrieved_by")
    if retrieved_by is not None:
        retrieved_by = _text(retrieved_by, f"{source}.provenance.retrieved_by")
    published_on = _parse_date(
        prov_node.get("published_on"), f"{source}.provenance.published_on", optional=True,
    )
    retrieved_at = None
    if prov_node.get("retrieved_at") is not None:
        raw_at = prov_node["retrieved_at"]
        if isinstance(raw_at, datetime):
            retrieved_at = raw_at
        elif isinstance(raw_at, str):
            try:
                retrieved_at = datetime.fromisoformat(raw_at.strip())
            except ValueError as exc:
                raise LedgerError(
                    f"expected an ISO-8601 timestamp, got {raw_at!r}",
                    f"{source}.provenance.retrieved_at",
                ) from exc
        else:
            raise LedgerError(
                f"expected an ISO-8601 timestamp, got {type(raw_at).__name__}",
                f"{source}.provenance.retrieved_at",
            )
    provenance = Provenance(
        source_url=source_url,
        source_tier=source_tier,
        publisher=publisher,
        published_on=published_on,
        isbn=isbn,
        retrieved_at=retrieved_at,
        retrieved_by=retrieved_by,
        archive_url=archive_url,
    )
    return provenance


def _validate_material_origin(
    provenance: Provenance,
    acquisition: str,
    storage: Storage,
    source: str,
) -> None:
    # A material with no traceable origin cannot be withdrawn later, which is
    # the one thing the ledger exists to make possible.
    if provenance.source_url is None and provenance.publisher is None and provenance.isbn is None:
        if acquisition != "generated":
            raise LedgerError(
                "provenance must record at least one of source_url / publisher / isbn so the "
                "material can be traced and withdrawn later",
                f"{source}.provenance",
            )
    # Held bytes must be locatable; a path with no provenance is an orphan.
    if storage.mode == "local_file" and storage.sha256 is None:  # pragma: no cover - guarded above
        raise LedgerError("local_file requires sha256", f"{source}.storage.sha256")


# --------------------------------------------------------------------------
# ledger file
# --------------------------------------------------------------------------


def validate_ledger(
    raw: Any,
    *,
    source: str = "<ledger>",
    subject_ids: frozenset[str] | None = None,
) -> tuple[Material, ...]:
    """Validate a whole ledger document (a list, or a mapping with ``items``)."""
    allowed_subjects = (
        subject_ids if subject_ids is not None else _subject_ids_for_validation()
    )
    if isinstance(raw, Mapping) and "items" in raw:
        _unknown(raw, {"schema_version", "items"}, source)
        declared = raw.get("schema_version", MATERIAL_SCHEMA_VERSION)
        version = _int(declared, f"{source}.schema_version", minimum=1)
        if version != MATERIAL_SCHEMA_VERSION:
            raise LedgerError(f"unsupported schema_version {version}", f"{source}.schema_version")
        entries = raw["items"]
    else:
        entries = raw

    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise LedgerError("expected a list of materials", f"{source}.items")

    materials = tuple(
        validate_material(
            entry,
            source=f"{source}.items[{index}]",
            subject_ids=allowed_subjects,
        )
        for index, entry in enumerate(entries)
    )

    seen: set[str] = set()
    for index, material in enumerate(materials):
        if material.resource_id in seen:
            raise LedgerError(
                f"duplicate resource_id {material.resource_id!r}",
                f"{source}.items[{index}].resource_id",
            )
        seen.add(material.resource_id)
    return materials


def _read_ledger_yaml(resolved: Path) -> Any:
    """Read one ledger file, reporting every read or parse failure as a ``LedgerError``.

    A ledger re-saved as GBK by a Windows editor used to escape as a raw
    ``UnicodeDecodeError`` traceback (round 152 S1). The shared strict loader rejects a
    key written twice instead of keeping only the last one, so a second ``rights:`` block
    can no longer silently replace the first (round 152 S2).
    """
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LedgerError(f"cannot read YAML: {exc}", resolved.as_posix()) from exc
    try:
        return load_yaml_text(text, source=resolved.as_posix())
    except ContractError as exc:
        raise LedgerError(exc.message, exc.path) from exc


def load_ledger(
    path: str | Path,
    *,
    subject_ids: frozenset[str] | None = None,
) -> tuple[Material, ...]:
    resolved = Path(path)
    if not resolved.is_file():
        raise LedgerError(f"file does not exist: {resolved}")
    if yaml is None:  # pragma: no cover
        raise LedgerError("PyYAML is required to read the ledger")
    raw = _read_ledger_yaml(resolved)
    allowed_subjects = (
        subject_ids if subject_ids is not None else _subject_ids_for_validation()
    )
    return validate_ledger(
        raw,
        source=resolved.as_posix(),
        subject_ids=allowed_subjects,
    )


# --------------------------------------------------------------------------
# queries used by downstream stages
# --------------------------------------------------------------------------


def structurable_materials(materials: Sequence[Material]) -> tuple[Material, ...]:
    """Materials that may currently authorise a derived knowledge point."""
    return tuple(m for m in materials if m.may_be_structured())


def evidence_capable_materials(materials: Sequence[Material]) -> tuple[Material, ...]:
    """Materials that can be cited with a verifiable ``path + sha256``."""
    return tuple(m for m in materials if m.can_back_evidence())


def integrity_report(
    materials: Sequence[Material], *, root: str | Path | None = None
) -> tuple[tuple[str, bool], ...]:
    """``(resource_id, bytes_verified)`` for every locally stored material.

    Remote references report ``False``: they hold no bytes, so their integrity
    is not merely unverified but unverifiable.
    """
    return tuple((m.resource_id, m.verify_bytes(root)) for m in materials)


def ledger_summary(materials: Sequence[Material]) -> dict[str, Any]:
    """Machine-readable overview used by the CLI and by reports."""
    return {
        "total": len(materials),
        "by_kind": _count(m.material_kind for m in materials),
        "by_rights_status": _count(m.rights.status for m in materials),
        "by_review_status": _count(m.review_status for m in materials),
        "structurable": [m.resource_id for m in structurable_materials(materials)],
        "evidence_capable": [m.resource_id for m in evidence_capable_materials(materials)],
        "unclear_rights": [m.resource_id for m in materials if not m.rights.is_clear()],
    }


def _count(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
