"""M13 one-time migration of frozen M7 delivery rows; see ``contracts/vocabulary.md``.

Public entry point: ``main``. Dry-run is the default; ``--apply`` writes completion events.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ky.schedule.completion import CompletionEvent, VocabProgress
from ky.models import ContractError
from ky.schedule.vocab_channel import VocabChannelError, import_delivery_baseline_with_dates
from ky.storage.day_plan_store import DayPlanStore, StorageError
from ky.workspace import find_workspace, load_workspace


def migrate_delivery(db: Path, store: DayPlanStore, *, apply: bool) -> tuple[CompletionEvent, ...]:
    """Plan or write one event per legacy delivery date, refusing occupied dates."""
    by_day: dict[date, list[str]] = defaultdict(list)
    for delivered_on, word_form in import_delivery_baseline_with_dates(db):
        day = date.fromisoformat(delivered_on)
        if word_form not in by_day[day]:
            by_day[day].append(word_form)

    events = tuple(
        CompletionEvent(day=day, vocab=VocabProgress(delivered_words=tuple(words)))
        for day, words in sorted(by_day.items())
    )
    occupied = [event.day for event in events if store.load_completion_event(event.day)]
    if occupied:
        dates = ", ".join(day.isoformat() for day in occupied)
        raise StorageError(f"completion event already exists for migration date(s): {dates}")
    if apply:
        for event in events:
            store.write_completion_event(event)
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace")
    parser.add_argument("--db", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        workspace = load_workspace(find_workspace(explicit=args.workspace))
        db = args.db or workspace.require("reference.vocabulary_db")
        events = migrate_delivery(db, DayPlanStore(workspace.plans), apply=args.apply)
    except (ContractError, OSError, ValueError, StorageError, VocabChannelError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2

    mode = "Applied" if args.apply else "DRY RUN"
    print(f"{mode}: {len(events)} completion event(s)")
    for event in events:
        print(f"{event.day.isoformat()}: {len(event.vocab.delivered_words)} word(s)")
    if not args.apply:
        print("No state was written. Use --apply after review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
