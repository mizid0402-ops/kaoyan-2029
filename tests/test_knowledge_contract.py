from __future__ import annotations

import copy
import unittest

from ky.knowledge import (
    ACTOR_DETERMINISTIC_SCRIPT,
    KnowledgePointError,
    apply_deterministic_frequency,
    eligible_for_exam_metrics,
    eligible_for_frequency,
    transition_knowledge_point,
    validate_knowledge_point,
)


SOURCE = {"path": "materials/outline.pdf", "sha256": "a" * 64, "locator": {"page": 3, "section": "limits"}}


def point(source_kind: str = "official_outline") -> dict:
    return {
        "schema_version": 1, "knowledge_point_id": "math1.limit.demo", "title": "极限",
        "status": "raw", "source_kind": source_kind, "sources": [SOURCE],
        "evidence": [], "transition_history": [], "revision": 1,
    }


class KnowledgeContractTest(unittest.TestCase):
    def test_unknown_key_has_precise_path(self) -> None:
        raw = point(); raw["typo"] = True
        with self.assertRaises(KnowledgePointError) as ctx:
            validate_knowledge_point(raw)
        self.assertIn("<knowledge_point>.typo", str(ctx.exception))

    def test_frequency_requires_deterministic_provenance(self) -> None:
        raw = point(); raw["frequency"] = {"value": 2, "computed_by": "ai", "basis": "past papers", "as_of": "2026-09-12"}
        with self.assertRaises(KnowledgePointError) as ctx:
            validate_knowledge_point(raw)
        self.assertIn("frequency.computed_by", str(ctx.exception))
        written = apply_deterministic_frequency(raw, 2, basis="scripted count", as_of="2026-09-12", writer=ACTOR_DETERMINISTIC_SCRIPT)
        self.assertEqual(validate_knowledge_point(written).frequency["value"], 2)

    def test_frequency_reader_is_independent_of_writer_identity(self) -> None:
        raw = apply_deterministic_frequency(
            point(), 2, basis="scripted count", as_of="2026-09-12",
            writer=ACTOR_DETERMINISTIC_SCRIPT,
        )
        self.assertEqual(validate_knowledge_point(raw).frequency["value"], 2)

    def test_non_deterministic_actor_cannot_write_frequency(self) -> None:
        with self.assertRaises(KnowledgePointError):
            apply_deterministic_frequency(
                point(), 2, basis="scripted count", as_of="2026-09-12", writer="human"
            )

    def test_ai_generated_boundary(self) -> None:
        raw = point("ai_generated")
        raw["evidence"] = [{"validation": "guided", "result": "usable", "source": SOURCE}]
        ai_point = validate_knowledge_point(raw)
        self.assertFalse(eligible_for_frequency(ai_point))
        self.assertFalse(eligible_for_exam_metrics(ai_point))
        raw["evidence"] = [{"validation": "independent", "result": "pass", "source": SOURCE}]
        with self.assertRaises(KnowledgePointError):
            validate_knowledge_point(raw)

    def test_state_machine_requires_actor_and_preconditions(self) -> None:
        raw = point()
        with self.assertRaises(KnowledgePointError):
            transition_knowledge_point(raw, "reviewed", "human", source=SOURCE)
        extracted = transition_knowledge_point(raw, "extracted", "ai", source=SOURCE)
        with self.assertRaises(KnowledgePointError):
            transition_knowledge_point(extracted, "reviewed", "ai", source=SOURCE, evidence={"validation": "guided", "source": SOURCE})
        reviewed = transition_knowledge_point(extracted, "reviewed", "human", source=SOURCE, evidence={"validation": "independent", "source": SOURCE})
        self.assertEqual(reviewed["status"], "reviewed")
        approved = transition_knowledge_point(reviewed, "approved", "human", source=SOURCE, evidence={"validation": "independent", "source": SOURCE})
        self.assertEqual(validate_knowledge_point(approved).status, "approved")


if __name__ == "__main__":
    unittest.main()
