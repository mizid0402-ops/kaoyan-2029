from pathlib import Path
from collections import Counter
from bs4 import BeautifulSoup
import yaml

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe")
HTML = ROOT / "data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html"

def main():
    soup = BeautifulSoup(HTML.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    lines = ["heading_count=" + str(len(headings)), "distribution=" + str(Counter(x.name for x in headings))]
    for i, x in enumerate(headings):
        lines.append("%03d %s %s %s" % (i, x.name, x.get("id"), x.get_text(" ", strip=True)))
    (TMP / "archive2026_headings.txt").write_text("\n".join(lines), encoding="utf-8")
    sample = []
    for x in headings[4:8]:
        sample.append("H=" + x.get_text(" ", strip=True))
        p = x.parent
        sample.append("P=" + p.name + " class=" + str(p.get("class")))
        for child in p.children:
            if getattr(child, "name", None):
                sample.append("  child=" + child.name + " " + child.get_text(" ", strip=True)[:180])
        for sib in list(x.next_siblings)[:5]:
            if getattr(sib, "name", None):
                sample.append("S=" + sib.name + " " + sib.get_text(" ", strip=True)[:180])
    (TMP / "archive2026_sample.txt").write_text("\n".join(sample), encoding="utf-8")
    tree = yaml.safe_load((ROOT / "data/structured_materials/cs408/knowledge_tree.yaml").read_text(encoding="utf-8"))
    counts = Counter((x.get("scope"), x.get("knowledge_point_id", "").count(".")) for x in tree)
    tlines = ["nodes=" + str(len(tree)), "scope_depth=" + str(counts)]
    for x in tree:
        if x.get("scope") in {"section", "item"}:
            tlines.append(x.get("knowledge_point_id", "") + " | " + x.get("scope", "") + " | " + x.get("title", ""))
    (TMP / "tree_probe.txt").write_text("\n".join(tlines), encoding="utf-8")
    from pypdf import PdfReader
    pdf = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf")
    raw_pages = [x.extract_text() or "" for x in PdfReader(str(pdf)).pages]
    raw_lines = []
    for pi, page in enumerate(raw_pages, 1):
        raw_lines.append("=== PAGE %02d ===" % pi)
        raw_lines.extend("%03d %s" % (i, line) for i, line in enumerate(page.splitlines()))
    (TMP / "round22_raw_lines.txt").write_text("\n".join(raw_lines), encoding="utf-8")

if __name__ == "__main__":
    main()
