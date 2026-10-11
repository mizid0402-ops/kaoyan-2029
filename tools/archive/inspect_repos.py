"""Read the fetched GitHub repo metadata and contents listings.

Pure local read of `cache/evidence/cs408repos/` — no network. Prints what each
candidate repository actually contains so a human can judge provenance before any
file is taken.

Usage:  py -3.12 tools/archive/inspect_repos.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "cache" / "evidence" / "cs408repos"


def show(name: str, path: Path) -> None:
    print(f"=== {name} ===")
    if not path.is_file():
        print("  (not fetched)")
        print()
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(text[:1200])
        print()
        return
    if isinstance(data, dict) and "full_name" in data:
        for key in ("full_name", "description", "license", "created_at", "pushed_at",
                    "stargazers_count", "forks_count", "size", "default_branch"):
            print(f"  {key:20} {data.get(key)}")
    elif isinstance(data, list):
        for entry in data:
            size = entry.get("size", 0)
            print(f"  {entry.get('type', '?'):4} {size:>9} {entry.get('name')}")
    else:
        print(f"  {str(data)[:400]}")
    print()


def main() -> int:
    show("neville-studio/408-exam-paper", D / "api_github_com_repos_neville_studio_408_exam_paper.html")
    show("neville-studio/408-exam-paper (contents)", D / "api_github_com_repos_neville_studio_408_exam_paper_contents.html")
    show("suhan42/cs-408", D / "api_github_com_repos_suhan42_cs_408.html")
    show("suhan42/cs-408 (contents, 403?)", D / "api_github_com_repos_suhan42_cs_408_contents.html")
    show("youngflysky/KaoYanZhenTi-PDF README", D / "raw_githubusercontent_com_youngflysky_KaoYanZhenTi_PDF_main_README_md.html")
    show("rate-limit body sample", D / "api_github_com_repos_csseky_cskaoyan.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
