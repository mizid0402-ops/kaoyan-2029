"""M4 knowledge-point ports from ``contracts/knowledge_tree.md``.

Exports validated tree records, mutation helpers, and the M17 grammar-aware
``tree_parent`` query alongside the existing M6 hierarchy interfaces.
"""

from .corpus_window import (
    DEFAULT_CORPUS_WINDOW_YEARS,
    MAX_CORPUS_WINDOW_YEARS,
    MIN_CORPUS_WINDOW_YEARS,
    ExamYearVerdict,
    classify_exam_year,
    corpus_window,
    plan_corpus_years,
)
from .knowledge_point import (
    ACTOR_AI,
    ACTOR_DETERMINISTIC_SCRIPT,
    ACTOR_HUMAN,
    BLOCK_ASSESSABLE_SCOPES,
    DAY_ASSESSABLE_SCOPES,
    KNOWLEDGE_SCHEMA_VERSION,
    NON_EXAMINABLE_SCOPES,
    VALID_SCOPES,
    KnowledgePoint,
    KnowledgePointError,
    TRANSITION_RULES,
    apply_deterministic_frequency,
    block_verification_targets,
    eligible_for_exam_metrics,
    eligible_for_frequency,
    load_knowledge_points,
    load_knowledge_points_from_text,
    transition_knowledge_point,
    validate_knowledge_point,
    validate_transition,
)
from .hierarchy import (
    LearnableTree,
    learnable_tree,
    nearest_ancestor_with_scope,
    parent_id,
    tree_parent,
)

__all__ = [
    "ACTOR_AI",
    "ACTOR_DETERMINISTIC_SCRIPT",
    "ACTOR_HUMAN",
    "BLOCK_ASSESSABLE_SCOPES",
    "DAY_ASSESSABLE_SCOPES",
    "DEFAULT_CORPUS_WINDOW_YEARS",
    "KNOWLEDGE_SCHEMA_VERSION",
    "MAX_CORPUS_WINDOW_YEARS",
    "MIN_CORPUS_WINDOW_YEARS",
    "NON_EXAMINABLE_SCOPES",
    "VALID_SCOPES",
    "ExamYearVerdict",
    "KnowledgePoint",
    "KnowledgePointError",
    "LearnableTree",
    "TRANSITION_RULES",
    "apply_deterministic_frequency",
    "block_verification_targets",
    "classify_exam_year",
    "corpus_window",
    "eligible_for_exam_metrics",
    "eligible_for_frequency",
    "load_knowledge_points",
    "load_knowledge_points_from_text",
    "learnable_tree",
    "nearest_ancestor_with_scope",
    "parent_id",
    "plan_corpus_years",
    "transition_knowledge_point",
    "tree_parent",
    "validate_knowledge_point",
    "validate_transition",
]
