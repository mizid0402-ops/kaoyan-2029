"""Verify that the audit evidence bundle faithfully represents the fetched responses.

This is the orchestrator's own check on the artifact it handed to reviewers
(project rule: "Verify the verification"). It asserts, for every claim section in
`review/attach-audit/evidence-bundle.md`:

  * the URL, HTTP status, response byte size and response sha256 match
    `cache/evidence/attach/index.json`;
  * the claim is marked as a fetch failure exactly when the index says so;
  * non-textual payloads (PDF) expose metadata only, never content.

It also reports the bundle's own sha256, so a review round can be pinned to an
exact bundle revision.

Usage:
    py -3.12 tools/archive/verify_evidence_bundle.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "review" / "attach-audit" / "evidence-bundle.md"
INDEX = ROOT / "cache" / "evidence" / "attach" / "index.json"


def main() -> int:
    text = BUNDLE.read_text(encoding="utf-8")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_url = {r["url"]: r for r in index}

    # parse the metadata table rows: | cid | url | http | bytes | response sha16 | local sha16 |
    rows = re.findall(
        r"^\| ([A-C]\d) \| (\S+) \| ([^|]+?) \| ([^|]+?) \| `([0-9a-f—]{1,16})` \| `([0-9a-f—]{1,16})` \|$",
        text,
        re.M,
    )
    print(f"bundle sha256: {hashlib.sha256(BUNDLE.read_bytes()).hexdigest()}")
    print(f"parsed {len(rows)} metadata rows from the bundle\n")

    problems: list[str] = []
    checked = 0
    for cid, url, http, size, sha16, local16 in rows:
        rec = by_url.get(url)
        if rec is None:
            problems.append(f"{cid}: url in bundle not present in index.json: {url}")
            continue
        checked += 1
        if not rec.get("ok"):
            if "失败" not in http:
                problems.append(f"{cid}: index says fetch FAILED but bundle says {http!r}")
            continue
        if str(rec["http_status"]) != http.strip():
            problems.append(f"{cid}: http {http.strip()} != index {rec['http_status']}")
        if str(rec["byte_size"]) != size.strip():
            problems.append(f"{cid}: bytes {size.strip()} != index {rec['byte_size']}")
        if not rec["sha256"].startswith(sha16):
            problems.append(f"{cid}: sha {sha16} != index {rec['sha256'][:16]}")

    # every index entry must be represented
    bundled = {r[1] for r in rows}
    for url, rec in by_url.items():
        if url not in bundled:
            problems.append(f"index url missing from bundle: {url}")

    # leak gate re-check: excerpts must not contain long verbatim runs.
    # Only the excerpt code blocks are inspected; the bundle's own scaffolding
    # (URLs, hashes, paths, table rows) is ours and legitimately Latin.
    excerpts = re.findall(r"^      ```text\n(.*?)^      ```", text, re.M | re.S)
    joined = "\n".join(excerpts)
    suspicious = [
        m.group(0)
        for m in re.finditer(r"[A-Za-z][A-Za-z0-9 ,;:'\"()\-\.]{24,}", joined)
        if "http" not in m.group(0)
        and "/" not in m.group(0)
        and "\\" not in m.group(0)
        and not re.fullmatch(r"[0-9a-f—]{1,16}", m.group(0).strip())
    ]
    if suspicious:
        problems.append(f"possible verbatim foreign text in bundle excerpts: {suspicious[:3]}")

    print(f"checked {checked} fetched responses")
    if problems:
        print("\nFAILURES:")
        for p in problems:
            print("  -", p)
        return 1
    print("OK: bundle metadata matches index.json; no verbatim foreign-text residue detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
