from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml

from ky.models import ContractError
from ky.question_bank import (
    adapted_question_group_all_retired,
    append_question,
    adapted_question_input_data,
    create_adapted_question_input,
    load_question_bank,
    question_ref,
    retire_question,
    select_adapted_question,
    submit_staged_question,
    validate_question,
)
from ky.__main__ import planner_input_main, question_bank_main, review_questions_main
from ky.schedule.completion import CompletionEvent, ReviewCompletion
from ky.storage.day_plan_store import DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.models import validate_review_item
from ky.workspace import WORKSPACE_FILENAME, load_workspace

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / WORKSPACE_FILENAME
PARENT = "math1.demo.chapter"
POINT = f"{PARENT}.item"


def _question(sequence: int, **updates: object) -> dict:
    raw = {
        "schema_version": 1, "id": f"qb-{POINT}-{sequence:02d}",
        "knowledge_point_id": POINT, "difficulty": "basic", "basis": "syllabus",
        "based_on": [], "stem": f"题目 {sequence}", "answer": "答案",
        "validation": "guided", "created_by": "ai:test-model", "created_on": "2026-10-01",
    }
    raw.update(updates)
    return raw


def _node(point_id: str, title: str, scope: str = "item") -> dict:
    return {
        "schema_version": 1, "knowledge_point_id": point_id, "title": title,
        "scope": scope, "status": "raw", "source_kind": "manual",
        "sources": [{"path": "synthetic.pdf", "sha256": "0" * 64,
                     "locator": {"page": 1}}],
    }


def _workspace(
    root: Path, *, entries: list[dict] | None = None, register_bank: bool = True,
) -> Path:
    document = copy.deepcopy(yaml.safe_load(REGISTRY.read_text(encoding="utf-8")))
    document["subjects"] = {"math1": {"name": "Math", "tree_grammar": "flat"}}
    document["reference"]["knowledge_trees"] = {"math1": "trees/tree.yaml"}
    document["reference"]["syllabus_versions"] = {}
    document["reference"]["exam_indexes"] = {"math1": ["indexes/questions.json"]}
    document["reference"]["topic_weights"] = "weights/topic_weights.json"
    document["reference"]["paper_shapes"] = {}
    document["supplementary"] = {}
    document["settings"] = {"exam_config": "config.yaml"}
    document["state"] = {
        "review_queue": "state/review_queue", "plans": "state/plans",
    }
    if register_bank:
        document["state"]["question_bank"] = "data/personal/question_bank"
    document["staging"] = "staging"
    (root / "config.yaml").write_bytes(
        (ROOT / "tests/fixtures/config/config-minimal.yaml").read_bytes()
    )
    tree = root / "trees/tree.yaml"
    tree.parent.mkdir(parents=True)
    tree.write_text(yaml.safe_dump([
        _node(PARENT, "章", "chapter"), _node(POINT, "条目"),
        _node("math1.demo.tracker", "跟踪点", "subject"),
    ], allow_unicode=True, sort_keys=False), encoding="utf-8")
    index = root / "indexes/questions.json"
    index.parent.mkdir()
    index.write_text(json.dumps({"entries": entries or []}, ensure_ascii=False), encoding="utf-8")
    weights = root / "weights/topic_weights.json"
    weights.parent.mkdir()
    weights.write_text(json.dumps({"per_question": {}}), encoding="utf-8")
    path = root / WORKSPACE_FILENAME
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


class QuestionBankPortTests(unittest.TestCase):
    def test_shape_and_basis_contract(self) -> None:
        self.assertEqual(validate_question(_question(1))["id"], f"qb-{POINT}-01")
        cases = []
        unknown = _question(1)
        unknown["extra"] = True
        cases.append(unknown)
        cases.append(_question(1, basis="past_questions", based_on=[]))
        cases.append(_question(1, basis="syllabus", based_on=["q1"]))
        cases.append(_question(1, id="qb-wrong.point-01"))
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ContractError):
                    validate_question(raw)

    def test_question_bank_skips_own_temporary_and_rejects_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            append_question(root, _question(1))
            folder = root / POINT
            own_temp = folder / f".qb-{POINT}-02.yaml.ab12cd34.tmp"
            own_temp.write_bytes(b"interrupted writer output")
            # tempfile's random alphabet contains "_" as well (lead delta, sol 282 M4).
            retire_temp = folder / f".qb-{POINT}-01.retired.yaml.p_1q2r3s.tmp"
            retire_temp.write_bytes(b"interrupted retire output")

            self.assertEqual([item["id"] for item in load_question_bank(root)],
                             [f"qb-{POINT}-01"])
            (folder / "manual-notes.txt").write_text("keep rejecting", encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "unexpected file in question bank"):
                load_question_bank(root)

    def test_append_reads_existing_bank_yaml_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            append_question(root, _question(1))
            original_open = Path.open
            bank_yaml_reads = []

            def counted_open(path: Path, *args: object, **kwargs: object):
                if path.suffix == ".yaml" and path.parent == root / POINT:
                    bank_yaml_reads.append(path)
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", counted_open):
                append_question(root, _question(2))

            self.assertEqual(bank_yaml_reads, [root / POINT / f"qb-{POINT}-01.yaml"])

    def test_submission_dry_run_and_commit_share_bank_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            workspace = load_workspace(registry)
            bank = workspace.write_target("state.question_bank")
            append_question(bank, _question(1))
            _, digest = create_adapted_question_input(POINT, workspace_path=registry)
            staged = workspace.write_target("staging") / "question_bank/proposal.yaml"
            staged.parent.mkdir(parents=True)
            proposal = {**_question(1), "input_hash": digest}
            staged.write_text(yaml.safe_dump(proposal), encoding="utf-8")

            errors = []
            for dry_run in (True, False):
                with self.assertRaises(ContractError) as caught:
                    submit_staged_question(
                        staged, dry_run=dry_run, workspace_path=registry,
                    )
                errors.append(str(caught.exception))

            self.assertEqual(errors[0], errors[1])
            self.assertIn("expected next question id", errors[0])
            self.assertFalse((bank / POINT / f"qb-{POINT}-02.yaml").exists())

    def test_duplicate_yaml_keys_and_filename_mismatch_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / POINT
            folder.mkdir()
            bad = folder / "qb-wrong-01.yaml"
            bad.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")
            with self.assertRaises(ContractError):
                load_question_bank(root)
            bad.unlink()
            bad.write_text(yaml.safe_dump(_question(1), allow_unicode=True), encoding="utf-8")
            with self.assertRaises(ContractError):
                load_question_bank(root)

    def test_append_is_write_once_and_uses_next_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = append_question(root, _question(1))
            original = first.read_bytes()
            with self.assertRaises(ContractError):
                append_question(root, _question(1, stem="改写"))
            second = append_question(root, _question(2))
            self.assertEqual(first.read_bytes(), original)
            self.assertTrue(second.exists())
            self.assertEqual(len(load_question_bank(root)), 2)

    def test_retirement_is_write_once_skipped_and_allows_tenth_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for sequence in range(1, 10):
                append_question(root, _question(sequence))
            first_retirement = retire_question(
                root, f"qb-{POINT}-01", "答案有误", "2026-10-01",
            )
            original = first_retirement.read_bytes()
            with self.assertRaises(ContractError):
                retire_question(root, f"qb-{POINT}-01", "再次停用", "2026-10-02")
            with self.assertRaises(ContractError):
                retire_question(root, f"qb-{POINT}-99", "不存在", "2026-10-02")
            self.assertEqual(first_retirement.read_bytes(), original)
            bank = load_question_bank(root)
            self.assertTrue(bank[0]["retired"])
            self.assertEqual(select_adapted_question(bank, POINT, (), {})["id"],
                             f"qb-{POINT}-02")
            for sequence in range(2, 10):
                retire_question(root, f"qb-{POINT}-{sequence:02d}", "停用", "2026-10-01")
            tenth = append_question(root, _question(10))
            self.assertEqual(tenth.name, f"qb-{POINT}-10.yaml")
            self.assertEqual(
                sum(not item.get("retired", False) for item in load_question_bank(root)), 1,
            )

    def test_retirement_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            append_question(root, _question(1))
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            target = retire_question(
                root, f"qb-{POINT}-01", "答案有误", "2026-10-01", dry_run=True,
            )
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            self.assertFalse(target.exists())
            self.assertEqual(after, before)

    def test_retired_ancestor_questions_are_skipped_and_group_status_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            append_question(root, _question(1, knowledge_point_id=PARENT,
                                            id=f"qb-{PARENT}-01"))
            retire_question(root, f"qb-{PARENT}-01", "错误", "2026-10-01")
            bank = load_question_bank(root)
            self.assertIsNone(select_adapted_question(bank, POINT, (PARENT,), {}))
            self.assertTrue(adapted_question_group_all_retired(bank, POINT, (PARENT,)))

    def test_all_retired_own_group_does_not_fall_through_to_ancestor(self) -> None:
        # sol 272 F1: the nearest populated group decides; an all-retired own group asks
        # for new questions instead of serving the parent's question.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            append_question(root, _question(1))
            append_question(root, _question(1, knowledge_point_id=PARENT,
                                            id=f"qb-{PARENT}-01"))
            retire_question(root, f"qb-{POINT}-01", "答案错", "2026-10-01")
            bank = load_question_bank(root)
            self.assertIsNone(select_adapted_question(bank, POINT, (PARENT,), {}))
            self.assertTrue(adapted_question_group_all_retired(bank, POINT, (PARENT,)))

    def test_retire_cli_dry_run_success_and_contract_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            workspace = load_workspace(registry)
            bank = workspace.write_target("state.question_bank")
            append_question(bank, _question(1))
            retirement = bank / POINT / f"qb-{POINT}-01.retired.yaml"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = question_bank_main([
                    "retire", "--question", f"qb-{POINT}-01", "--reason", "答案有误",
                    "--date", "2026-10-01", "--dry-run", "--workspace", str(registry),
                ])
            self.assertEqual(code, 0)
            self.assertFalse(retirement.exists())
            with contextlib.redirect_stdout(io.StringIO()):
                code = question_bank_main([
                    "retire", "--question", f"qb-{POINT}-01", "--reason", "答案有误",
                    "--date", "2026-10-01", "--workspace", str(registry),
                ])
            self.assertEqual(code, 0)
            for question_id in (f"qb-{POINT}-01", f"qb-{POINT}-99"):
                with contextlib.redirect_stderr(io.StringIO()):
                    code = question_bank_main([
                        "retire", "--question", question_id, "--reason", "再次停用",
                        "--date", "2026-10-02", "--workspace", str(registry),
                    ])
                self.assertEqual(code, 2)

    def test_selection_uses_nearest_bank_and_cycles_unseen_then_oldest(self) -> None:
        questions = [_question(index) for index in (1, 2, 3)]
        selected = select_adapted_question(questions, POINT, (PARENT,), {})
        self.assertEqual(selected["id"], f"qb-{POINT}-01")
        selected = select_adapted_question(
            questions, POINT, (PARENT,), {f"qb-{POINT}-01": date(2026, 9, 1)}
        )
        self.assertEqual(selected["id"], f"qb-{POINT}-02")
        selected = select_adapted_question(
            questions, POINT, (PARENT,), {
                f"qb-{POINT}-01": date(2026, 9, 1),
                f"qb-{POINT}-02": date(2026, 9, 2),
            }
        )
        self.assertEqual(selected["id"], f"qb-{POINT}-03")
        selected = select_adapted_question(
            questions, POINT, (PARENT,), {
                f"qb-{POINT}-01": date(2026, 9, 1),
                f"qb-{POINT}-02": date(2026, 9, 2),
                f"qb-{POINT}-03": date(2026, 9, 3),
            }
        )
        self.assertEqual(selected["id"], f"qb-{POINT}-01")
        self.assertEqual(
            select_adapted_question([_question(1, knowledge_point_id=PARENT,
                                                id=f"qb-{PARENT}-01")],
                                    POINT, (PARENT,), {})["knowledge_point_id"], PARENT,
        )

    def test_syllabus_input_and_non_leaf_submission_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            workspace = load_workspace(registry)
            self.assertEqual(workspace.write_target("state.question_bank"),
                             root / "data/personal/question_bank")
            input_path, digest = create_adapted_question_input(PARENT, workspace_path=registry)
            package = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertEqual(package["basis"], "syllabus")
            staged = workspace.write_target("staging") / "question_bank/proposal.yaml"
            staged.parent.mkdir(parents=True)
            proposal = {**_question(1, knowledge_point_id=PARENT, id=f"qb-{PARENT}-01"),
                        "input_hash": digest}
            staged.write_text(yaml.safe_dump(proposal, allow_unicode=True), encoding="utf-8")
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            target, _ = submit_staged_question(staged, dry_run=True, workspace_path=registry)
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            self.assertIsNone(target)
            self.assertEqual(before, after)
            target, _ = submit_staged_question(staged, workspace_path=registry)
            self.assertTrue(target.is_file())

    def test_submission_rejects_stale_hash_and_non_candidate_basis(self) -> None:
        entry = {
            "question_id": "math1-2025-01", "subject_id": "math1", "exam_year": 2025,
            "number": 1, "knowledge_point_weights": {PARENT: 1.0},
            "locator": {"page": 1}, "question_type": "single_choice", "marks": 2,
            "answer": "A", "answer_kind": "letter",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root, entries=[entry])
            workspace = load_workspace(registry)
            _, digest = create_adapted_question_input(POINT, workspace_path=registry)
            package, _ = adapted_question_input_data(workspace, POINT)
            self.assertEqual(package["candidates"][0]["question_type"], "single_choice")
            staged = workspace.write_target("staging") / "question_bank/proposal.yaml"
            staged.parent.mkdir(parents=True)
            proposal = _question(1, basis="past_questions", based_on=["not-a-candidate"])
            staged.write_text(yaml.safe_dump({**proposal, "input_hash": digest},
                                             allow_unicode=True), encoding="utf-8")
            with self.assertRaises(ContractError):
                submit_staged_question(staged, workspace_path=registry)
            staged.write_text(yaml.safe_dump({**proposal, "based_on": ["math1-2025-01"],
                                              "input_hash": digest},
                                             allow_unicode=True), encoding="utf-8")
            entry["locator"] = {"page": 9}
            index_path = root / "indexes/questions.json"
            index_path.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
            with self.assertRaises(ContractError):
                submit_staged_question(staged, workspace_path=registry)

    def test_tracking_node_is_not_a_learnable_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            with self.assertRaises(ContractError):
                adapted_question_input_data(load_workspace(registry), "math1.demo.tracker")

    def test_review_questions_reads_qb_references_from_history(self) -> None:
        # sol 268 F1: completions record "qb:<id>"; 01 and 02 used, so 03 is next.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            workspace = load_workspace(registry)
            item = validate_review_item({
                "review_id": "review-low", "revision": 1, "subject_id": "math1",
                "knowledge_point_id": POINT, "title": "演示条目", "granularity": "concept",
                "state": "queued", "estimated_minutes": 10, "introduced_on": "2026-09-01",
                "due_date": "2026-10-01", "last_reviewed_on": None,
                "schedule": {"mode": "fixed_bootstrap", "phase": 1, "interval_days": 3,
                              "ease_factor": 2.5, "repetitions": 1, "lapses": 0},
                "defer_count": 0, "last_quality": None, "self_rating": None,
            })
            ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
            bank = workspace.write_target("state.question_bank")
            for sequence in (1, 2, 3):
                append_question(bank, _question(sequence))
            store = DayPlanStore(workspace.write_target("state.plans"))
            for day, sequence in ((date(2026, 9, 28), 1), (date(2026, 9, 29), 2)):
                store.write_completion_event(CompletionEvent(day, (ReviewCompletion(
                    "review-low", day, check="exercise", outcome="correct",
                    question_ref=question_ref(f"qb-{POINT}-{sequence:02d}"),
                ),)))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = review_questions_main([
                    "--date", "2026-10-01", "--workspace", str(registry), "--json",
                ])
            self.assertEqual(code, 0)
            review = json.loads(output.getvalue())["reviews"][0]
            self.assertEqual(review["question_ref"], f"qb:qb-{POINT}-03")

    def test_unquoted_yaml_date_is_accepted_and_stored_as_iso_string(self) -> None:
        # sol 268 F2: the spec / prompt example writes created_on as a YAML date.
        raw = yaml.safe_load(yaml.safe_dump(_question(1)).replace(
            "created_on: '2026-10-01'", "created_on: 2026-10-01"))
        self.assertIsInstance(raw["created_on"], date)
        self.assertEqual(validate_question(raw)["created_on"], "2026-10-01")

    def test_review_questions_uses_tier_and_excludes_completed_question(self) -> None:
        entries = [
            {"question_id": f"math1-2025-0{number}", "subject_id": "math1",
             "exam_year": 2025, "number": number,
             "knowledge_point_weights": {POINT: 1.0}, "locator": {"page": number}}
            for number in (1, 2)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root, entries=entries)
            workspace = load_workspace(registry)
            item = validate_review_item({
                "review_id": "review-one", "revision": 1, "subject_id": "math1",
                "knowledge_point_id": POINT, "title": "演示条目", "granularity": "concept",
                "state": "queued", "estimated_minutes": 10, "introduced_on": "2026-09-01",
                "due_date": "2026-10-01", "last_reviewed_on": None,
                "schedule": {"mode": "sm2_lite", "phase": 5, "interval_days": 7,
                              "ease_factor": 2.5, "repetitions": 2, "lapses": 0},
                "defer_count": 0, "last_quality": None, "self_rating": None,
            })
            ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
            DayPlanStore(workspace.write_target("state.plans")).write_completion_event(
                CompletionEvent(date(2026, 9, 30), (ReviewCompletion(
                    "review-one", date(2026, 9, 30), check="past_question", outcome="incorrect",
                    question_ref="math1-2025-01",
                ),))
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = review_questions_main([
                    "--date", "2026-10-01", "--workspace", str(registry), "--json",
                ])
            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            review = payload["reviews"][0]
            self.assertEqual(review["level"], "progressing")
            self.assertEqual(review["question_ref"], "math1-2025-02")
            self.assertEqual(review["check"], "past_question")

    def test_cli_generates_input_and_submits_adapted_question(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = planner_input_main([
                    "--kind", "adapted-questions", "--knowledge-point", PARENT,
                    "--workspace", str(registry),
                ])
            self.assertEqual(code, 0)
            lines = output.getvalue().splitlines()
            input_path = Path(lines[0].removeprefix("input: "))
            digest = lines[1].removeprefix("input_hash: ")
            proposal = {
                **_question(1, knowledge_point_id=PARENT, id=f"qb-{PARENT}-01"),
                "input_hash": digest,
            }
            staged = root / "staging/question_bank/proposal.yaml"
            staged.parent.mkdir(parents=True)
            staged.write_text(yaml.safe_dump(proposal, allow_unicode=True), encoding="utf-8")
            before = root / "data/personal/question_bank"
            self.assertFalse(before.exists())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = question_bank_main([
                    "submit", "--from-staging", str(staged), "--dry-run",
                    "--workspace", str(registry),
                ])
            self.assertEqual(code, 0)
            self.assertFalse(before.exists())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = question_bank_main([
                    "submit", "--from-staging", str(staged), "--workspace", str(registry),
                ])
            self.assertEqual(code, 0)
            self.assertTrue((before / PARENT / f"qb-{PARENT}-01.yaml").is_file())
            self.assertTrue(input_path.is_file())

    def test_submit_without_question_bank_registration_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root, register_bank=False)
            _, digest = create_adapted_question_input(PARENT, workspace_path=registry)
            staged = root / "staging/question_bank/proposal.yaml"
            staged.parent.mkdir(parents=True)
            proposal = {
                **_question(1, knowledge_point_id=PARENT, id=f"qb-{PARENT}-01"),
                "input_hash": digest,
            }
            staged.write_text(yaml.safe_dump(proposal, allow_unicode=True), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = question_bank_main([
                    "submit", "--from-staging", str(staged), "--workspace", str(registry),
                ])
            self.assertEqual(code, 2)
            self.assertIn("state.question_bank", stderr.getvalue())

    def test_review_questions_learned_uses_adapted_question_and_missing_bank_message(self) -> None:
        for registered in (True, False):
            with self.subTest(registered=registered), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                registry = _workspace(root, register_bank=registered)
                workspace = load_workspace(registry)
                item = validate_review_item({
                    "review_id": "review-learned", "revision": 1, "subject_id": "math1",
                    "knowledge_point_id": POINT, "title": "演示条目", "granularity": "concept",
                    "state": "queued", "estimated_minutes": 10, "introduced_on": "2026-09-01",
                    "due_date": "2026-10-01", "last_reviewed_on": None,
                    "schedule": {"mode": "fixed_bootstrap", "phase": 1, "interval_days": 3,
                                  "ease_factor": 2.5, "repetitions": 1, "lapses": 0},
                    "defer_count": 0, "last_quality": None, "self_rating": None,
                })
                ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
                if registered:
                    append_question(workspace.write_target("state.question_bank"), _question(1))
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = review_questions_main([
                        "--date", "2026-10-01", "--workspace", str(registry), "--json",
                    ])
                self.assertEqual(code, 0)
                review = json.loads(output.getvalue())["reviews"][0]
                if registered:
                    self.assertEqual(review["question_level"], "adapted")
                    self.assertEqual(review["check"], "exercise")
                    self.assertEqual(review["question_ref"], f"qb:qb-{POINT}-01")
                else:
                    self.assertEqual(review["status"], "未登记题库")

    def test_review_questions_reports_missing_question_when_bank_and_candidates_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            workspace = load_workspace(registry)
            item = validate_review_item({
                "review_id": "review-empty", "revision": 1, "subject_id": "math1",
                "knowledge_point_id": POINT, "title": "演示条目", "granularity": "concept",
                "state": "queued", "estimated_minutes": 10, "introduced_on": "2026-09-01",
                "due_date": "2026-10-01", "last_reviewed_on": None,
                "schedule": {"mode": "sm2_lite", "phase": 5, "interval_days": 7,
                              "ease_factor": 2.5, "repetitions": 2, "lapses": 0},
                "defer_count": 0, "last_quality": None, "self_rating": None,
            })
            ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = review_questions_main([
                    "--date", "2026-10-01", "--workspace", str(registry), "--json",
                ])
            self.assertEqual(code, 0)
            review = json.loads(output.getvalue())["reviews"][0]
            self.assertEqual(review["status"], "缺题")

    def test_retired_question_review_message_and_text_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            workspace = load_workspace(registry)
            item = validate_review_item({
                "review_id": "review-retired", "revision": 1, "subject_id": "math1",
                "knowledge_point_id": POINT, "title": "演示条目", "granularity": "concept",
                "state": "queued", "estimated_minutes": 10, "introduced_on": "2026-09-01",
                "due_date": "2026-10-01", "last_reviewed_on": None,
                "schedule": {"mode": "fixed_bootstrap", "phase": 1, "interval_days": 3,
                              "ease_factor": 2.5, "repetitions": 1, "lapses": 0},
                "defer_count": 0, "last_quality": None, "self_rating": None,
            })
            ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
            bank = workspace.write_target("state.question_bank")
            append_question(bank, _question(1))
            retire_question(bank, f"qb-{POINT}-01", "错误", "2026-10-01")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = review_questions_main([
                    "--date", "2026-10-01", "--workspace", str(registry), "--json",
                ])
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            review = payload["reviews"][0]
            self.assertIn("缺改编题：先生成", review["status"])
            self.assertIn("该点改编题已全部停用", review["status"])
            self.assertEqual(set(payload), {"date", "reviews"})
            self.assertEqual(set(review), {
                "review_id", "knowledge_point_id", "title", "level", "status",
                "generation_command",
            })

            # An active adapted question gets the retire instruction only in text output.
            append_question(bank, _question(2))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = review_questions_main([
                    "--date", "2026-10-01", "--workspace", str(registry),
                ])
            self.assertEqual(code, 0)
            self.assertIn(
                "有问题可停用：py -3.12 -m ky question-bank retire --question "
                f'qb-{POINT}-02 --reason "替换为原因" --date 2026-10-01',
                output.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
