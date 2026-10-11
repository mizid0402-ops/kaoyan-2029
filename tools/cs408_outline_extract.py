"""M4 CS408 outline extraction and normalization helpers.

Contract: ``contracts/knowledge_tree.md``. Public functions: ``clean_display``,
``key``, ``subject_chunks``, ``extract_2022``, ``extract_2026``, ``flatten``,
``compare`` and ``tree_reverse_check``.

Historical input paths
are supplied by callers so current code does not bind to a machine cache.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import yaml
from bs4 import BeautifulSoup
from pypdf import PdfReader


SUBJECTS = {
    "数据结构": "ds",
    "计算机组成原理": "co",
    "操作系统": "os",
    "计算机网络": "cn",
}


def clean_display(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[一二三四五六七八九十]+\s*[、.]\s*", "", s)
    s = re.sub(r"^[（(]\s*[一二三四五六七八九十]+\s*[）)〕]\s*[.]?\s*", "", s)
    s = re.sub(r"^(?:\d+\s*[.]|[⒈⒉⒊⒋⒌⒍⒎⒏⒐])\s*", "", s)
    s = re.sub(r"^\d+\s+(?=[\u3400-\u9fff])", "", s)
    return s.strip()


def key(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    s = s.replace("1/o", "i/o").replace("l/o", "i/o")
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[，。；：、,.;:()（）\[\]【】/\\·'\"“”‘’]", "", s)
    return s


def subject_chunks(text: str):
    starts = []
    for name in SUBJECTS:
        pos = text.find(name + "考研大纲")
        if pos < 0:
            raise ValueError("subject not found: " + name)
        starts.append((pos, name))
    starts.sort()
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        yield name, text[pos:end]


def extract_2022(pdf_path: Path):
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))
    pages = [unicodedata.normalize("NFKC", p.extract_text() or "") for p in reader.pages]
    text = "\f".join(pages)
    normalized_pages = [
        "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in p.splitlines()).strip()
        for p in pages
    ]
    normalized = "\n".join(normalized_pages)
    chapter_re = re.compile(r"(?<![一二三四五六七八九十])([一二三四五六七八九十]{1,3})\s*、\s*")
    section_re = re.compile(
        r"(?<![A-Za-z0-9])[(（]\s*([一二三四五六七八九十—-]{1,3})"
        r"\s*[)）〕\]]\s*[.]?"
    )
    item_re = re.compile(
        r"(?<![A-Za-z0-9])(?:\d{1,2}\s*[.]|"
        r"\d{1,2}(?=\s+[\u3400-\u9fff])|"
        r"[⒈⒉⒊⒋⒌⒍⒎⒏⒐]|(?<!\w)-(?=[\u3400-\u9fffA-Za-z]))"
    )
    subjects = {}
    for name, chunk in subject_chunks(normalized):
        if name == "计算机网络":
            chunk = re.split(r"2021\s*考纲变化|2022\s*考纲变化", chunk, maxsplit=1)[0]
        chapters = []
        cm = list(chapter_re.finditer(chunk))
        for ci, m in enumerate(cm):
            cstart = m.end()
            cend = cm[ci + 1].start() if ci + 1 < len(cm) else len(chunk)
            cbody = chunk[cstart:cend]
            sm = list(section_re.finditer(cbody))
            sections = []
            for si, smatch in enumerate(sm):
                sstart = smatch.end()
                send = sm[si + 1].start() if si + 1 < len(sm) else len(cbody)
                sbody = cbody[sstart:send].lstrip()
                first_nl = sbody.find("\n")
                im_all = list(item_re.finditer(sbody))
                if first_nl >= 0 and (not im_all or im_all[0].start() >= first_nl):
                    stitle = clean_display(sbody[:first_nl])
                    item_body = sbody[first_nl + 1 :]
                else:
                    first_item = im_all[0].start() if im_all else len(sbody)
                    stitle = clean_display(sbody[:first_item])
                    item_body = sbody[first_item:]
                im = list(item_re.finditer(item_body))
                items = []
                unnumbered = []
                if im:
                    for ii, imatch in enumerate(im):
                        istart = imatch.end()
                        iend = im[ii + 1].start() if ii + 1 < len(im) else len(item_body)
                        title = clean_display(item_body[istart:iend])
                        if title:
                            items.append(title)
                # A section without explicit numbered entries is retained as a
                # section only; prose is not promoted to an entry.
                sections.append({"title": stitle, "items": items, "unnumbered": unnumbered})
            chapters.append({
                "title": clean_display(cbody[:sm[0].start()] if sm else cbody),
                "sections": sections,
            })
        subjects[name] = {"code": SUBJECTS[name], "chapters": chapters}
    return {
        "metadata": {
            "path": str(pdf_path),
            "bytes": pdf_path.stat().st_size,
            "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "pages": len(reader.pages),
            "chars_joined_with_formfeeds": len(text),
            "chars_joined_with_newlines": len(normalized),
        },
        "normalized_source_text": normalized,
        "subjects": subjects,
    }


def extract_2026(html_path: Path):
    html_path = Path(html_path)
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    root = soup.select_one(".markdown-content") or soup
    children = [x for x in root.find_all(recursive=False)]
    subjects = {}
    current_subject = None
    current_chapter = None
    current_section = None
    for x in children:
        text = x.get_text(" ", strip=True)
        if x.name == "h2" and text.startswith(("一、", "二、", "三、", "四、")):
            subject_name = text.split("、", 1)[1].strip()
            subject_name = subject_name.replace("输入/输出", "输入/输出")
            current_subject = subject_name
            subjects[current_subject] = {"code": SUBJECTS[current_subject], "chapters": []}
            current_chapter = None
            current_section = None
        elif x.name == "h3" and text != "考查目标":
            current_chapter = {"title": clean_display(text), "sections": []}
            subjects[current_subject]["chapters"].append(current_chapter)
            current_section = None
        elif x.name == "h3" and text == "考查目标":
            current_section = None
        elif x.name == "h4":
            current_section = {"title": clean_display(text), "items": [], "unnumbered": []}
            current_chapter["sections"].append(current_section)
        elif x.name == "ol" and current_section is not None:
            for li in x.find_all("li", recursive=False):
                t = clean_display(li.get_text(" ", strip=True))
                if t:
                    current_section["items"].append(t)
        elif x.name == "p" and current_section is not None:
            t = clean_display(text)
            if t:
                current_section["unnumbered"].append(t)
    return {"subjects": subjects}


def flatten(data, field="items"):
    result = {}
    for name, subj in data["subjects"].items():
        chapters = [x["title"] for x in subj["chapters"]]
        sections = [x["title"] for c in subj["chapters"] for x in c["sections"]]
        items = [x for c in subj["chapters"] for s in c["sections"] for x in s[field]]
        result[name] = {"chapters": chapters, "sections": sections, "items": items}
    return result


def compare(a, b):
    out = {}
    for name in SUBJECTS:
        aa, bb = a[name], b[name]
        aset = {key(x): x for x in aa["items"]}
        bset = {key(x): x for x in bb["items"]}
        ach = {key(x) for x in aa["chapters"]}
        bch = {key(x) for x in bb["chapters"]}
        both = set(aset) & set(bset)
        only_a = set(aset) - set(bset)
        only_b = set(bset) - set(aset)
        out[name] = {
            "2022_chapters": len(aa["chapters"]),
            "2026_chapters": len(bb["chapters"]),
            "2022_sections": len(aa["sections"]),
            "2026_sections": len(bb["sections"]),
            "2022_items": len(aa["items"]),
            "2026_items": len(bb["items"]),
            "2022_max_depth": 3 if aa["items"] else 2,
            "2026_max_depth": 3 if bb["items"] else 2,
            "chapter_intersection": len(ach & bch),
            "chapter_union": len(ach | bch),
            "chapter_jaccard": len(ach & bch) / len(ach | bch),
            "both": len(both),
            "only_2022": [aset[k] for k in sorted(only_a)],
            "only_2026": [bset[k] for k in sorted(only_b)],
            "both_titles_2022": [aset[k] for k in sorted(both)],
        }
    return out


def tree_reverse_check(data2022, tree_path: Path):
    tree = yaml.safe_load(Path(tree_path).read_text(encoding="utf-8"))
    items = [x for x in tree if x.get("scope") == "item"]
    corpus = {
        key(title): (name, title)
        for name, subject in data2022["subjects"].items()
        for chapter in subject["chapters"]
        for section in chapter["sections"]
        for title in section["items"]
    }
    full_source = key(data2022.get("normalized_source_text", ""))
    exact = []
    missing = []
    item_keys = set(corpus)
    section_keys = {
        key(s["title"])
        for name, subj in data2022["subjects"].items()
        for chapter in subj["chapters"]
        for s in chapter["sections"]
    }
    covered = []
    for x in items:
        k = key(x.get("title", ""))
        target = exact if k in corpus else missing
        target.append({
            "id": x.get("knowledge_point_id"),
            "title": x.get("title"),
            "match": corpus.get(k),
        })
        sub = any(k in y or y in k for y in item_keys)
        in_source = k in full_source
        in_section = k in section_keys
        covered.append({
            "id": x.get("knowledge_point_id"),
            "title": x.get("title"),
            "subject": x.get("knowledge_point_id", "").split(".")[1],
            "exact_item": k in corpus,
            "substring_item": sub,
            "exact_section": in_section,
            "in_full_source": in_source,
            "covered": k in corpus or sub or in_section,
            "covered_full_source": k in corpus or sub or in_section or in_source,
        })
    by_subject = {}
    for code in SUBJECTS.values():
        rows = [x for x in covered if x["subject"] == code]
        by_subject[code] = {
            "tree_items": len(rows),
            "exact": sum(x["exact_item"] for x in rows),
            "covered_by_item_substring": sum(x["covered"] for x in rows),
            "covered_by_full_source": sum(x["covered_full_source"] for x in rows),
            "uncovered_titles": [x["title"] for x in rows if not x["covered_full_source"]],
        }
    return {
        "tree_nodes": len(tree),
        "tree_items": len(items),
        "exact_item_matches": exact,
        "missing_items": missing,
        "coverage": covered,
        "by_subject": by_subject,
    }
