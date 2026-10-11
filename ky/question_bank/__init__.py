"""M31 adapted-question bank ports from ``contracts/question_bank.md``.

Public interfaces: :func:`validate_question`, :func:`load_question_bank`,
:func:`append_question`, :func:`retire_question`, :func:`select_adapted_question`,
:func:`question_ref`, :func:`question_id_from_ref`, and the adapted-input
creation and staged-submission functions.
"""

from .port import (
    append_question,
    adapted_question_input_data,
    adapted_question_group_all_retired,
    create_adapted_question_input,
    load_question_bank,
    question_id_from_ref,
    question_ref,
    retire_question,
    select_adapted_question,
    submit_staged_question,
    validate_question,
)

__all__ = [
    "append_question",
    "adapted_question_input_data",
    "adapted_question_group_all_retired",
    "create_adapted_question_input",
    "load_question_bank",
    "question_id_from_ref",
    "question_ref",
    "retire_question",
    "select_adapted_question",
    "submit_staged_question",
    "validate_question",
]
