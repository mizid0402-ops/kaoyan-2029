from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html"
OUT = ROOT / "data/structured_materials/cs408/knowledge_tree.yaml"


class MarkdownParser(HTMLParser):
    CAPTURE = {"h2", "h3", "h4", "li", "p"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.captures: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.list_stack: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "ol":
            start = 1
            for key, value in attrs:
                if key == "start" and value:
                    start = int(value)
            self.list_stack.append(start)
        if tag in self.CAPTURE:
            self.captures.append({"tag": tag, "buf": []})

    def handle_data(self, data: str) -> None:
        for capture in self.captures:
            capture["buf"].append(data)  # type: ignore[union-attr]

    def handle_endtag(self, tag: str) -> None:
        if tag == "ol" and self.list_stack:
            self.list_stack.pop()
        if tag in self.CAPTURE:
            for index in range(len(self.captures) - 1, -1, -1):
                if self.captures[index]["tag"] == tag:
                    capture = self.captures.pop(index)
                    text = "".join(capture["buf"]).strip()  # type: ignore[arg-type]
                    number = None
                    if tag == "li" and self.list_stack:
                        number = self.list_stack[-1]
                        self.list_stack[-1] += 1
                    self.events.append({"tag": tag, "text": text, "number": number})
                    break


def content_html(raw: str) -> str:
    start = raw.index('<div class="outline-markdown">')
    end = raw.index("</div></article>", start)
    return raw[start:end]


def slug_subject(title: str) -> str:
    return {"一、数据结构": "ds", "二、计算机组成原理": "co", "三、操作系统": "os", "四、计算机网络": "cn"}[title]


def main() -> None:
    raw = SOURCE.read_text(encoding="utf-8")
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    parser = MarkdownParser()
    parser.feed(content_html(raw))

    nodes: list[dict[str, object]] = []
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    current_subject = ""
    subject_code = ""
    chapter_no = 0
    section_no = 0
    detail_no = 0
    search_cursor = raw.index('<div class="outline-markdown">')
    objective_no = 0
    subject_event_no = 0
    chapter_titles: list[tuple[str, str]] = []
    section_titles: list[tuple[str, str, str]] = []

    def add_node(title: str, kind: str, locator_section: str, node_id: str, quote_ref: str | None = None) -> None:
        nonlocal search_cursor
        quote = quote_ref or title
        offset = raw.find(quote, search_cursor)
        if offset < 0:
            offset = raw.find(quote, raw.index('<div class="outline-markdown">'))
        if offset < 0:
            raise RuntimeError(f"cannot locate source text: {quote!r}")
        search_cursor = offset + len(quote)
        source = {
            "path": "data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html",
            "sha256": digest,
            "locator": {"section": locator_section, "offset": offset, "quote_ref": quote},
        }
        nodes.append(
            {
                "schema_version": 1,
                "knowledge_point_id": node_id,
                "title": title,
                "status": "extracted",
                "source_kind": "official_outline",
                "sources": [source],
                "evidence": [],
                "transition_history": [
                    {"from": "raw", "to": "extracted", "actor": "ai", "source": source}
                ],
                "revision": 1,
            }
        )
        counts[subject_code][kind] += 1

    for event in parser.events:
        tag = event["tag"]
        text = str(event["text"])
        if tag == "h2":
            current_subject = text
            subject_code = slug_subject(text)
            subject_event_no += 1
            chapter_no = section_no = detail_no = objective_no = 0
            add_node(text, "subject", text, f"cs408.{subject_code}.subject")
        elif tag == "h3":
            if text == "考查目标":
                objective_no += 1
                add_node(text, "objective_group", current_subject + " > 考查目标", f"cs408.{subject_code}.exam-objectives")
            else:
                chapter_no += 1
                section_no = detail_no = 0
                chapter_titles.append((current_subject, text))
                add_node(text, "chapter", current_subject + " > " + text, f"cs408.{subject_code}.chapter-{chapter_no:02d}")
        elif tag == "h4":
            section_no += 1
            detail_no = 0
            section_titles.append((current_subject, chapter_titles[-1][1], text))
            add_node(text, "section", current_subject + " > " + chapter_titles[-1][1] + " > " + text, f"cs408.{subject_code}.chapter-{chapter_no:02d}.section-{section_no:02d}")
        elif tag in {"li", "p"}:
            detail_no += 1
            number = event["number"]
            title = f"{number}. {text}" if number is not None else text
            chapter_part = f"chapter-{chapter_no:02d}" if chapter_no else "exam-objectives"
            section_part = f"section-{section_no:02d}" if section_no else "objective"
            kind = "list_item" if tag == "li" else "detail"
            section_label = current_subject
            if chapter_titles and chapter_no:
                section_label += " > " + chapter_titles[-1][1]
            if section_titles and section_no:
                section_label += " > " + section_titles[-1][2]
            add_node(title, kind, section_label, f"cs408.{subject_code}.{chapter_part}.{section_part}.detail-{detail_no:02d}", quote_ref=text)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(yaml.safe_dump(nodes, allow_unicode=True, sort_keys=False, width=120))
    print("sha256", digest)
    print("total", len(nodes))
    for subject in ("ds", "co", "os", "cn"):
        print(subject, dict(counts[subject]))
    print("tags", Counter(str(event["tag"]) for event in parser.events))
    print("chapters", len(chapter_titles), "sections", len(section_titles))


if __name__ == "__main__":
    main()
