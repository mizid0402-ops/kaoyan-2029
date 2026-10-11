from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/raw_materials/cs408/syllabus"


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active: list[tuple[str, list[str]]] = []
        self.events: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h2", "h3", "h4", "li", "p"}:
            self.active.append((tag, []))

    def handle_data(self, data: str) -> None:
        for _, buf in self.active:
            buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.active) - 1, -1, -1):
            if self.active[index][0] == tag:
                event_tag, buf = self.active.pop(index)
                self.events.append((event_tag, "".join(buf).strip()))
                return


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("（", "(").replace("）", ")")


def main() -> None:
    tree = yaml.safe_load((ROOT / "data/structured_materials/cs408/knowledge_tree.yaml").read_text(encoding="utf-8"))
    archive = (BASE / "archive408_408_outline_2026.html").read_text(encoding="utf-8")
    xdf = (BASE / "xdf_408_outline_2026.html").read_text(encoding="utf-8")
    hep = (BASE / "hep_408_outline_analysis_2026.html").read_text(encoding="utf-8")
    archive_body = archive[archive.index('<div class="outline-markdown">'):]
    parser = TextParser()
    parser.feed(archive_body)
    print("archive tags", Counter(tag for tag, _ in parser.events))
    print("archive titles", len(tree))
    missing_exact = []
    missing_normalized = []
    for node in tree:
        quote = node["sources"][0]["locator"]["quote_ref"]
        if quote not in xdf:
            missing_exact.append((node["knowledge_point_id"], node["title"], quote))
            if norm(quote) not in norm(xdf):
                missing_normalized.append((node["knowledge_point_id"], node["title"], quote))
    print("xdf missing exact", len(missing_exact))
    for item in missing_exact:
        print("XDF", item)
    print("xdf missing normalized", len(missing_normalized))
    for item in missing_normalized:
        print("XDF-NORM", item)
    hep_li = re.findall(r"<li>([^<>]+)", hep)
    hep_catalog = [x.strip() for x in hep_li if x.strip().startswith(("第", "1.", "2.", "3.", "4.", "5.", "6."))]
    print("hep catalog entries", len(hep_catalog))
    for item in hep_catalog:
        print("HEP", item)


if __name__ == "__main__":
    main()
