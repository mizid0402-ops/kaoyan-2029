"""M16 localhost HTML server; see contracts/web.md.

Public interface: ``make_server``. Rendering helpers are module-private.
Business data crosses the M33 ports (today view, queue view), M26
(``set_day_minutes``), and read-only M11 / M28 / M8 for the route page plus the
``products.charts`` directory for the chart pages (sol 293 / 295 suggestion).
"""

from __future__ import annotations

import html
import re
import sys
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlsplit

from ky.availability import set_day_minutes
from ky.models import ContractError, load_config
from ky.pacing.port import (
    cycle_for_date, load_pacing_report_state, settings_for_workspace,
)
from ky.schedule.budget import daily_base_minutes
from ky.storage.route_store import RoutePlanStore
from ky.today import advance_recorded_day, load_queue_view, load_today, record_day
from ky.today.record import RecordPipelineError
from ky.workspace import Workspace

_POST_LOCK = threading.Lock()
_MAX_BODY = 64 * 1024
_MESSAGES = {
    "saved": "已保存", "cleared": "已清除", "recorded": "已记录",
    "advanced": "已推进复习队列", "already_advanced": "已经推进过，无需再补",
}


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _tier_label(level: str) -> str:
    # sol 293 R1: queue and today views share one mastery display mapping.
    labels = {"learned": "学过", "progressing": "掌握中", "consolidated": "已巩固"}
    return labels.get(level, level)


def _page(title: str, body: str, status: int = 200, *, readonly: bool = False
          ) -> tuple[int, bytes]:
    nav = ("<nav><a href='/'>今天</a> · <a href='/queue'>复习队列</a> · "
           "<a href='/route'>路线与复盘</a> · <a href='/charts'>图表</a> · "
           "<a href='/'>回到今天</a></nav>")
    content = nav + body if readonly else body
    document = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{_esc(title)}</title>
<style>
:root{{color-scheme:light dark;font:16px/1.55 system-ui,sans-serif}}
body{{max-width:900px;margin:auto;padding:1rem;background:Canvas;color:CanvasText}}
section,article{{border:1px solid GrayText;border-radius:.5rem;padding:1rem;margin:1rem 0}}
input,button,select{{font:inherit;padding:.45rem;margin:.2rem}}
label{{display:inline-block;margin:.3rem}}.muted{{opacity:.75}}
.row{{padding:.5rem 0;border-bottom:1px solid GrayText}}
tr[aria-current='step']{{outline:2px solid Highlight;font-weight:700}}
@media(max-width:600px){{body{{padding:.6rem}}}}
</style><body><main>{content}</main></body></html>"""
    return status, document.encode("utf-8")


def _failure(message: str, status: int = 400) -> tuple[int, bytes]:
    return _page("请求未完成", f"<h1>请求未完成</h1><p>{_esc(message)}</p><a href='/'>返回</a>", status)


def _readonly_page(title: str, body: str, status: int = 200) -> tuple[int, bytes]:
    return _page(title, body, status, readonly=True)


def _render_queue(view) -> tuple[int, bytes]:
    body = []
    if view["freeze"]:
        body.append(_render_queue_freeze(view["freeze"]))
    body.append(f"<h1>{_esc(view['date'])} 复习队列</h1>")
    if (not any(bucket["count"] for bucket in view["buckets"].values())
            and view["ahead"]["count"] == 0):
        body.append("<p>复习队列是空的（学完知识点后用 <code>ky learn</code> 入队）</p>")
    body.append(_render_queue_budget(view))
    body.append(_render_queue_buckets(view["buckets"]))
    body.append(_render_queue_items("今天入选", view["selected"]))
    body.append(_render_queue_backlog(
        view["backlog"], view["buckets"]["deferred"]["count"],
    ))
    body.append(_render_queue_ahead(view["ahead"]))
    return _readonly_page("复习队列", "".join(body))


def _render_queue_budget(view) -> str:
    budget, caps = view["budget"], view["caps"]
    body = ["<section><h2>今天的时间</h2><p>" + _esc(view["date"]) + "；总计 " +
            _esc(budget["total_minutes"]) + " 分钟（" +
            _esc(_source_label(budget["total_source"])) + "）；基数 " +
            _esc(budget["base_minutes"]) + " 分钟（" +
            _esc(_source_label(budget["base_source"])) + "）</p><p>复习软 / 硬上限：" +
            _esc(caps["soft_target_minutes"]) + " / " +
            _esc(caps["hard_cap_minutes"]) + " 分钟</p>"]
    body.append("</section>")
    return "".join(body)


def _render_queue_freeze(freeze):
    return ("<section><h2>复习冻结</h2><p>积压 " +
            _esc(freeze.get("overdue_minutes", 0)) + " 分钟；阈值 " +
            _esc(freeze.get("threshold_minutes", 0)) +
            " 分钟。请让 AI 运行 <code>ky resume</code>。</p></section>")


def _render_queue_buckets(buckets) -> str:
    labels = {"selected": "今天入选", "deferred": "延期",
              "unschedulable": "单项太大", "scheduled_ahead": "未到期",
              "unreachable": "过期但不可选"}
    rows = ["<section><h2>队列分类</h2>"]
    for name in ("selected", "deferred", "unschedulable", "scheduled_ahead",
                 "unreachable"):
        value = buckets[name]
        rows.append("<p>" + _esc(labels[name]) + "：" + _esc(value["count"]) +
                    " 项，" + _esc(value["minutes"]) + " 分钟</p>")
        if name == "unschedulable":
            rows.append("<p>单项太大，请拆分</p>")
    rows.append("</section>")
    return "".join(rows)


def _render_queue_items(title: str, items, deferred_count: int = 0) -> str:
    if not items:
        return ""
    rows = ["<section><h2>" + _esc(title) + "</h2>"]
    for index, item in enumerate(items):
        rows.append("<article><h3>" + _esc(item["title"]) + "</h3><p>" +
                    _esc(item["review_id"]) + " · " + _esc(item["subject_name"]) +
                    " · " + _esc(_tier_label(item["level"])) + " · 知识点 " +
                    _esc(item["knowledge_point_id"]) + "</p><p>到期 " +
                    _esc(item["due_date"]) + "；逾期 " + _esc(item["overdue_days"]) +
                    " 天；延期 " + _esc(item["defer_count"]) + " 次；遗忘 " +
                    _esc(item["lapses"]) + " 次；预计 " +
                    _esc(item["estimated_minutes"]) + " 分钟</p>")
        if index < deferred_count:
            rows.append("<p>defer_count 是本次预检延期后计数</p>")
        rows.append("</article>")
    rows.append("</section>")
    return "".join(rows)


def _render_queue_backlog(backlog, deferred_count: int) -> str:
    body = ["<section><h2>积压：" + _esc(backlog["count"]) + " 项，" +
            _esc(backlog["minutes"]) + " 分钟</h2>"]
    for subject, total in backlog["by_subject"].items():
        body.append("<p>" + _esc(subject) + "：" + _esc(total["count"]) +
                    " 项，" + _esc(total["minutes"]) + " 分钟</p>")
    body.append(_render_queue_items("积压明细", backlog["details"], deferred_count))
    if backlog["remaining_count"]:
        body.append("<p>其余 " + _esc(backlog["remaining_count"]) + " 项未展开</p>")
    body.append("</section>")
    return "".join(body)


def _render_queue_ahead(ahead) -> str:
    dates = "、".join(ahead["due_dates"]) or "无"
    return ("<section><h2>未来队列</h2><p>" + _esc(ahead["count"]) +
            " 项；最近到期日：" + _esc(dates) + "</p></section>")


def _route_view(workspace, day):
    route = (RoutePlanStore(workspace.write_target("state.routes")).current()
             if workspace.routes is not None else None)
    config = load_config(workspace.require("settings.exam_config"))
    pacing = settings_for_workspace(workspace)
    base, source = daily_base_minutes(day, config, route, pacing)
    cycle = cycle_for_date(pacing, day) if pacing is not None else None
    report_state = ({"missing": (), "reports": {}} if pacing is None else
                    _route_reports(pacing, day, workspace))
    return route, base, source, cycle, pacing, report_state


def _route_reports(pacing, day, workspace):
    missing, reports = load_pacing_report_state(
        pacing, day, workspace.write_target("state.plans"),
    )
    return {"missing": missing, "reports": reports}


def _render_route(workspace, day) -> tuple[int, bytes]:
    route, base, source, cycle, pacing, reports = _route_view(workspace, day)
    body = ["<h1>路线与复盘 · " + _esc(day.isoformat()) + "</h1>"]
    body.append(_render_route_plan(route, day))
    body.append(_render_route_pacing(base, source, cycle, pacing, reports))
    return _readonly_page("路线与复盘", "".join(body))


def _render_route_plan(route, day):
    if route is None:
        return ("<section><h2>路线</h2><p>还没有路线，请让 AI 按 "
                "<code>prompts/route_planning.md</code> 写提案</p></section>")
    left = max(0, (route.target_exam_date - day).days)
    body = ["<section><h2>路线</h2><p>" + _esc(route.route_id) + "；修订 " +
            _esc(route.revision) + "；规划输入标识 " +
            _esc(route.stage1_input_hash[:12]) + "；起始 " +
            _esc(route.start_date.isoformat()) + "；目标考试日 " +
            _esc(route.target_exam_date.isoformat()) + "；剩余 " + _esc(left) + " 天</p>",
            "<table><thead><tr><th>阶段</th><th>起止</th><th>标签</th>"
            "<th>复习分钟</th><th>目标</th></tr></thead><tbody>"]
    for index, phase in enumerate(route.phases):
        current = phase.start <= day < phase.end_exclusive
        values = ", ".join(f"{_esc(key)} {_esc(value)} 分钟"
                            for key, value in phase.review_minutes.items())
        targets = ("未设目标" if phase.targets is None else
                   ", ".join(f"{_esc(key)} {_esc(value)}" for key, value
                              in phase.targets.items()))
        body.append("<tr" + (" aria-current='step'" if current else "") +
                    "><td>" + _esc(index + 1) + "</td><td>" +
                    _esc(phase.start.isoformat()) + " – " +
                    _esc(phase.end_exclusive.isoformat()) + "（右开）</td><td>" +
                    _esc(phase.label) + "</td><td>" + values + "</td><td>" +
                    targets + "</td></tr>")
    body.append("</tbody></table></section>")
    return "".join(body)


def _render_route_pacing(base, source, cycle, pacing, reports):
    if pacing is None:
        return "<section><h2>复盘</h2><p>未登记复盘设置</p></section>"
    body = ["<section><h2>复盘</h2><p>当前基数 " + _esc(base) +
            " 分钟（" + _esc(_source_label(source)) + "）</p>"]
    if cycle is None:
        body.append("<p>复盘尚未开始；下个复盘日：空</p>")
    else:
        body.append("<p>周期 " + _esc(cycle.start.isoformat()) + " 至 " +
                    _esc(cycle.end.isoformat()) + "；下个复盘日 " +
                    _esc(cycle.end.isoformat()) + "</p>")
    missing = sorted(reports["missing"], key=lambda item: item.end)
    if missing:
        body.append("<p>未报告周期：" + _esc(", ".join(
            item.end.isoformat() for item in missing)) + "</p>")
    saved = reports["reports"]
    if not saved:
        body.append("<p>还没有复盘报告</p>")
    else:
        latest = max(saved)
        report = saved[latest]
        body.append(_render_latest_report(latest, report))
    body.append("</section>")
    return "".join(body)


def _render_latest_report(day_text, report):
    base = report.get("base", {})
    values = " / ".join(_esc(base.get(key, "")) for key in ("min", "max", "mean"))
    body = ["<h3>最近报告：" + _esc(day_text) + "</h3><p>基数 min / max / mean：" +
            values + " 分钟</p>"]
    for subject, stats in report.get("reviews", {}).items():
        if isinstance(stats, dict):
            counts = "；".join(
                _esc(key) + " " + _esc(stats.get(key, 0))
                for key in ("completed", "correct", "partial", "incorrect", "none")
            )
            body.append("<p>" + _esc(subject) + "：" + counts + "</p>")
        else:
            body.append("<p>" + _esc(subject) + "：" + _esc(stats) + "</p>")
    return "".join(body)


_CHART_PATTERNS = (
    ("week", re.compile(r"^week--.+\.html$")),
    ("progress", re.compile(r"^progress--.+\.html$")),
    ("ability", re.compile(r"^ability--.+\.html$")),
)


def _charts_directory(workspace):
    path = workspace.products.get("charts")
    if path is None:
        return None
    if not path.exists():
        return path
    return workspace.require("products.charts")


def _chart_files(path):
    files = {name: [] for name, _pattern in _CHART_PATTERNS}
    for filename in path.iterdir():
        if filename.is_symlink() or not filename.is_file():
            continue
        for category, pattern in _CHART_PATTERNS:
            if pattern.fullmatch(filename.name):
                files[category].append(filename)
                break
    for matches in files.values():
        matches.sort(key=lambda item: (-item.stat().st_mtime_ns, item.name))
    return files


def _render_charts(workspace) -> tuple[int, bytes]:
    path = _charts_directory(workspace)
    if path is None:
        body = "<h1>图表</h1><p>未登记图表目录，请让 AI 检查注册表</p>"
        return _readonly_page("图表", body)
    if not path.exists():
        return _readonly_page("图表", _charts_generation_hint())
    try:
        files = _chart_files(path)
    except OSError as exc:
        raise ContractError(f"cannot list chart directory: {exc}",
                            "products.charts") from exc
    body = ["<h1>图表</h1>"]
    any_html = any(files.values())
    if not any_html:
        body.append(_charts_generation_hint())
    for category, _pattern in _CHART_PATTERNS:
        if not files[category]:
            continue
        body.append("<section><h2>" + _esc(category) + "</h2>")
        for filename in files[category]:
            modified = date.fromtimestamp(filename.stat().st_mtime).isoformat()
            link = "/charts/" + quote(filename.name, safe="")
            body.append("<p><a href='" + _esc(link) + "'>" +
                        _esc(filename.name) + "</a> · " + _esc(modified) + "</p>")
        body.append("</section>")
    script = path / "plotly.min.js"
    if any_html and not _ordinary_chart_file(path, script):
        body.append("<p>图表脚本缺失，请重新生成图表</p>")
    return _readonly_page("图表", "".join(body))


def _charts_generation_hint():
    return ("<h1>图表</h1><p>尚无匹配图表，请运行 "
            "<code>ky chart week</code>、<code>ky chart progress</code>、"
            "<code>ky chart ability</code> 生成。</p>")


def _ordinary_chart_file(root: Path, path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return path.resolve(strict=True).parent == root.resolve(strict=True)
    except (OSError, RuntimeError):
        return False


def _chart_response(workspace, encoded_name):
    name = unquote(encoded_name, errors="strict")
    if ("/" in name or "\\" in name or name in {".", ".."}
            or ".." in name.split("/")):
        return 404, "<h1>文件不存在</h1>".encode("utf-8"), "text/html; charset=utf-8"
    path = _charts_directory(workspace)
    if path is None or not path.exists() or not path.is_dir():
        return 404, "<h1>文件不存在</h1>".encode("utf-8"), "text/html; charset=utf-8"
    if name == "plotly.min.js":
        content_type = "application/javascript; charset=utf-8"
    elif any(pattern.fullmatch(name) for _category, pattern in _CHART_PATTERNS):
        content_type = "text/html; charset=utf-8"
    else:
        return 404, "<h1>文件不存在</h1>".encode("utf-8"), "text/html; charset=utf-8"
    target = path / name
    if not _ordinary_chart_file(path, target):
        return 404, "<h1>文件不存在</h1>".encode("utf-8"), "text/html; charset=utf-8"
    try:
        return 200, target.read_bytes(), content_type
    except OSError as exc:
        raise ContractError(f"cannot read chart file: {exc}", "products.charts") from exc


def _render(view, today: date, msg: str | None = None) -> tuple[int, bytes]:
    day = date.fromisoformat(view["date"])
    readonly = day != today
    body = [_render_header(day, today), _render_freeze_section(view)]
    body.append(_render_time_section(view))
    body.append(_render_reviews_section(view))
    body.append(_render_record_section(view, day, readonly))
    body.append(_render_availability_section(view, day, today))
    body.append(_render_pacing_section(view))
    if msg in _MESSAGES:
        body.insert(1, f"<p role='status'>{_esc(_MESSAGES[msg])}</p>")
    return _page("今天", "".join(body))


def _render_header(day: date, today: date) -> str:
    heading = f"<h1>{_esc(day.isoformat())}（周{_esc('一二三四五六日'[day.weekday()])}）</h1>"
    if day == today:
        return heading
    return heading + "<p>只读：不是今天　<a href='/'>回到今天</a></p>"


def _render_freeze_section(view) -> str:
    freeze = view["preflight"].get("freeze")
    if not freeze:
        return ""
    return (
        "<section><h2>复习冻结</h2>积压 " +
        _esc(freeze.get("overdue_minutes", 0)) + " 分钟；阈值 " +
        _esc(freeze.get("threshold_minutes", 0)) +
        " 分钟。请让 AI 运行 <code>ky resume</code>。</section>"
    )


def _render_pacing_section(view) -> str:
    pacing = view.get("pacing")
    if pacing is None:
        return ""
    body = ["<section><h2>复盘</h2>"]
    cycle_end = pacing.get("next_review")
    if cycle_end:
        end = date.fromisoformat(cycle_end)
        body.append("<p>本周期到 " + _esc(cycle_end) + " 结束，" +
                    _esc((end + timedelta(days=1)).isoformat()) + " 复盘</p>")
    cycles = pacing.get("unreported_cycles", [])
    if cycles:
        body.extend(("<p>尚未出报告：", _esc(", ".join(cycles)),
                     "；请让 AI 出复盘报告。</p>"))
    body.append("</section>")
    return "".join(body)


def _render_time_section(view) -> str:
    budget = view["budget"]
    preflight = view["preflight"]
    body = []
    body.append("<section><h2>今天的时间</h2><p>总计："+
                _esc(budget["total_minutes"])+" 分钟（"+
                _esc(_source_label(budget["total_source"]))+
                "）；基数："+_esc(budget["base_minutes"])+" 分钟（"+
                _esc(_source_label(budget["base_source"]))+"）</p>")
    preflight = view["preflight"]
    body.append("<p>复习："+_esc(preflight.get("review_minutes", 0))+
                " 分钟；软上限 "+_esc(preflight.get("soft_target_minutes", 0))+
                " 分钟；硬上限 "+_esc(preflight.get("hard_cap_minutes", 0))+
                " 分钟</p>")
    for allocation in preflight.get("subject_allocation", []):
        body.append("<p>"+_esc(allocation.get("display_name", ""))+" 新学："+
                    _esc(allocation.get("new_content_minutes", 0))+" 分钟</p>")
    quotas = preflight.get("subject_review_quotas")
    if quotas is not None:
        used = preflight.get("subject_review_minutes", {})
        names = {item["subject_id"]: item.get("display_name", item["subject_id"])
                 for item in preflight.get("subject_allocation", [])}
        for subject, minutes in quotas.items():
            body.append("<p>"+_esc(names.get(subject, subject))+" 复习配额："+_esc(minutes)+
                        " 分钟；已用 "+_esc(used.get(subject, 0))+" 分钟</p>")
    timetable = view.get("timetable")
    if timetable:
        body.append("<p>第 "+_esc(timetable["week"])+" 周；"+
                    _esc(timetable["blocks"])+" 大节；空闲 "+
                    _esc(timetable["free_minutes"])+" 分钟</p>")
    phase = view.get("route_phase")
    if phase:
        body.append("<p>路线阶段："+_esc(phase["label"])+"</p>")
    body.append("</section>")
    return "".join(body)


def _render_reviews_section(view) -> str:
    preflight = view["preflight"]
    body = ["<section><h2>今天的复习</h2>"]
    subjects = {item["review_id"]: item["subject_id"]
                for item in preflight.get("selected", [])}
    subject_names = {item["subject_id"]: item["display_name"]
                     for item in preflight.get("subject_allocation", [])}
    if not view["reviews"]:
        body.append("<p>今天没有入选复习项。</p>")
    for item in view["reviews"]:
        body.append("<article><h3>"+_esc(item.get("title", ""))+"</h3><p>"+
                    _esc(subject_names.get(subjects.get(item["review_id"], ""),
                                           subjects.get(item["review_id"], "")))+" · "+
                    _esc(_tier_label(item.get("level", "")))+
                    "</p>")
        question = item.get("question")
        if item.get("question_level") == "past_question" or item.get("check") == "past_question":
            body.append(_render_past_question(item, question))
        elif item.get("question_level") == "adapted" or item.get("check") == "exercise":
            body.append(_render_adapted_question(question))
        else:
            body.append("<p>还没有改编题，请让 AI 补题</p>")
        body.append("</article>")
    body.append("<p>延期："+_esc(len(view["preflight"].get("deferred", [])))+
                " 项；无法安排："+
                _esc(len(view["preflight"].get("unschedulable", [])))+" 项</p>")
    body.append("</section>")
    return "".join(body)


def _render_past_question(item, metadata) -> str:
    """Show a true-question reference and locator metadata, never metadata as a stem."""
    question_ref = item.get("question_ref", "")
    parts = ["<p>真题：" + _esc(question_ref) + "</p>"]
    if isinstance(metadata, dict):
        year = metadata.get("exam_year")
        number = metadata.get("number")
        if year is not None or number is not None:
            parts.append("<p>年份 / 题号：" + _esc(year or "未知") + " / " +
                         _esc(number or "未知") + "</p>")
    return "".join(parts)


def _render_adapted_question(question) -> str:
    if not isinstance(question, dict):
        return "<p>还没有改编题，请让 AI 补题</p>"
    body = ["<p>" + _esc(question.get("question", question.get("stem", ""))) + "</p>"]
    for option in question.get("choices", question.get("options", [])):
        body.append("<p>" + _esc(option) + "</p>")
    if "answer" in question:
        body.append("<details><summary>答案</summary>" +
                    _esc(question["answer"]) + "</details>")
    return "".join(body)


def _render_record_section(view, day: date, readonly: bool) -> str:
    body = []
    recorded = view.get("recorded")
    if recorded is not None:
        if not recorded["advanced"]:
            # sol 283 M3: keep durable results visible while queue advance is pending.
            body.append(
                "<section><h2>已记录，复习队列未推进</h2>"
                "<form method='post' action='/advance'><input type='hidden' "
                "name='date' value='" + _esc(day.isoformat()) +
                "'><button>补推进复习队列</button></form></section>"
            )
        minutes = recorded.get("study_minutes")
        minutes_text = "未填写" if minutes is None else f"{minutes} 分钟"
        body.append("<section><h2>记录结果</h2><p>学习分钟："+
                    _esc(minutes_text)+"</p>")
        for result in recorded["reviews"]:
            body.append("<p>"+_esc(result["review_id"])+"："+
                        _esc({"correct": "对", "partial": "半对",
                              "incorrect": "错"}.get(result["outcome"], result["outcome"]))+
                        "</p>")
        body.append("</section>")
    elif not readonly:
        body.append("<section><h2>记录今天</h2><form method='post' action='/record'>")
        body.append("<input type='hidden' name='date' value='"+_esc(day.isoformat())+
                    "'><input type='hidden' name='view_hash' value='"+
                    _esc(view["view_hash"])+"'>")
        for item in view["reviews"]:
            rid = _esc(item["review_id"])
            body.append("<fieldset><legend>"+_esc(item.get("title", rid))+"</legend>")
            if not item.get("question") and not item.get("question_ref"):
                body.append("<p>没有题目：先默写，再对照笔记；下面选的是对照后的结果</p>")
            for value, label in (("skip", "没做"), ("correct", "对"),
                                 ("partial", "半对"), ("incorrect", "错")):
                if (value != "skip" and not item.get("question")
                        and not item.get("question_ref")):
                    label = "对照后：" + label
                body.append(f"<label><input type='radio' name='outcome.{rid}' value='{value}'"+
                            (" checked" if value == "skip" else "")+
                            f">{label}</label>")
            body.append("</fieldset>")
        body.append(
            "<label>学习分钟 <input type='number' min='0' max='1440' "
            "name='study_minutes'></label>"
            "<button>记录今天（一天只能交一次）</button></form></section>"
        )
    return "".join(body)


def _render_availability_section(view, day: date, today: date) -> str:
    if not view.get("availability_registered") or day < today:
        return ""
    body = ["<section><h2>改可用分钟</h2><p>填写值优先于课表和基数；清除后回到课表 / 基数。"
            "保存会按规范格式重写文件，文件里的注释不保留。</p><form method='post' action='/availability'>"
            "<input type='hidden' name='date' value='"+_esc(day.isoformat())+
            "'><label>分钟 <input type='number' min='0' max='1440' name='minutes'></label>"
            "<button>保存</button></form><form method='post' action='/availability'>"
            "<input type='hidden' name='date' value='"+_esc(day.isoformat())+
            "'><input type='hidden' name='clear' value='1'><button>清除</button></form></section>"]
    return "".join(body)


def _read_form(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    if handler.headers.get_content_type() != "application/x-www-form-urlencoded":
        raise ContractError("只接受表单请求", "Content-Type")
    length = int(handler.headers.get("Content-Length", "-1"))
    if length < 0 or length > _MAX_BODY:
        raise ContractError("请求内容长度无效", "Content-Length")
    form = parse_qs(handler.rfile.read(length).decode("utf-8"),
                    keep_blank_values=True, strict_parsing=True)
    if any(len(values) != 1 for values in form.values()):
        raise ContractError("字段不能重复", "form")
    return {key: values[0] for key, values in form.items()}


def _post_availability(workspace: Workspace, values: dict[str, str], today: date) -> str:
    if set(values) not in ({"date", "minutes"}, {"date", "clear"}):
        raise ContractError("表单字段无效", "form")
    day = _parse_date(values["date"])
    if day < today:
        raise ContractError("只能修改今天及以后的日期", "date")
    if "clear" in values:
        if values["clear"] != "1":
            raise ContractError("clear must be 1", "clear")
        minutes = None
        message = "cleared"
    else:
        minutes = _parse_minutes(values["minutes"])
        message = "saved"
    if workspace.availability is None:
        raise ContractError("未登记可用时间文件", "state.availability")
    set_day_minutes(workspace.write_target("state.availability"), day, minutes)
    return message


def _post_record(workspace: Workspace, values: dict[str, str], today: date) -> str:
    allowed = {"date", "view_hash", "study_minutes"}
    outcomes = {}
    submitted_review_ids = []
    for key, value in values.items():
        if key.startswith("outcome."):
            allowed.add(key)
            submitted_review_ids.append(key[8:])
            if value != "skip":
                outcomes[key[8:]] = value
    if set(values) - allowed or not {"date", "view_hash"} <= set(values):
        raise ContractError("表单字段无效", "form")
    day = _parse_date(values["date"])
    if day != today:
        raise ContractError("只能记录今天", "date")
    minutes_text = values.get("study_minutes", "")
    minutes = None if minutes_text == "" else _parse_minutes(minutes_text)
    record_day(workspace, day, outcomes, study_minutes=minutes,
               expected_view_hash=values["view_hash"],
               submitted_review_ids=submitted_review_ids)
    return "recorded"


def _post_advance(workspace: Workspace, values: dict[str, str]) -> str:
    if set(values) != {"date"}:
        raise ContractError("表单字段无效", "form")
    day = _parse_date(values["date"])
    result = advance_recorded_day(workspace, day)
    return "advanced" if result["advanced_review_ids"] else "already_advanced"


def _post_route(workspace: Workspace, path: str, values: dict[str, str], today: date) -> str:
    if path == "/availability":
        return _post_availability(workspace, values, today)
    if path == "/record":
        return _post_record(workspace, values, today)
    if path == "/advance":
        return _post_advance(workspace, values)
    raise LookupError(path)


def _failure_response(exc: RecordPipelineError, day: date | None) -> tuple[int, bytes]:
    if exc.stage == "freeze_written":
        message = ("冻结已触发并记下，但今天的记录没有保存，请排除故障后重新记录："
                   + str(exc))
        return 400, _failure(message)[1]
    if exc.stage == "event_written":
        submitted = (day or date.today()).isoformat()
        content = ("<h1>已记录，复习队列未推进</h1><p>" + _esc(str(exc)) +
                   "</p><form method='post' action='/advance'><input type='hidden' "
                   "name='date' value='" + _esc(submitted) + "'><button>补推进复习队列" 
                   "</button></form><a href='/'>返回</a>")
        return 400, _page("复习队列未推进", content)[1]
    return 400, _failure(str(exc))[1]


def make_server(workspace: Workspace, port: int = 8730, *,
                today_provider: Callable[[], date] = date.today) -> ThreadingHTTPServer:
    """Create a testable localhost-only server for an already loaded workspace."""
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes,
                  content_type: str = "text/html; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_only_path(self, path: str) -> bool:
            return path in {"/queue", "/route", "/charts"} or path.startswith("/charts/")

        def _method_not_allowed(self) -> None:
            body = "<html lang='zh-CN'><meta charset='utf-8'><p>此页面只接受 GET</p></html>"
            encoded = body.encode("utf-8")
            self.send_response(405)
            self.send_header("Allow", "GET")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            try:
                parsed = urlsplit(self.path)
                path = parsed.path
                if path in {"/queue", "/route", "/charts"}:
                    query = parse_qs(parsed.query, keep_blank_values=True,
                                     strict_parsing=True) if parsed.query else {}
                    if path == "/charts":
                        if query:
                            raise ContractError("图表页不接受查询字段", "query")
                        status, body = _render_charts(workspace)
                        self._send(status, body)
                        return
                    if set(query) - {"date"} or any(len(values) != 1
                                                    for values in query.values()):
                        raise ContractError("只接受一个 date 查询字段", "query")
                    day = (today_provider() if "date" not in query
                           else _parse_date(query["date"][0]))
                    if path == "/queue":
                        self._send(*_render_queue(load_queue_view(workspace, day)))
                    else:
                        self._send(*_render_route(workspace, day))
                    return
                if path.startswith("/charts/"):
                    if parsed.query:
                        raise ContractError("图表文件不接受查询字段", "query")
                    status, body, content_type = _chart_response(
                        workspace, path[len("/charts/"):],
                    )
                    self._send(status, body, content_type)
                    return
                if path != "/":
                    self._send(404, _failure("页面不存在", 404)[1])
                    return
                query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
                if set(query) - {"date", "msg"} or any(len(v) != 1 for v in query.values()):
                    raise ContractError("未知查询字段", "query")
                today = today_provider()
                day = today if "date" not in query else _parse_date(query["date"][0])
                view = load_today(workspace, day)
                status, body = _render(view, today, query.get("msg", [None])[0])
                self._send(status, body)
            except (ValueError, ContractError) as exc:
                self._send(400, _failure(str(exc))[1])
            except Exception as exc:  # normal server errors stay concise in the browser
                print(f"web GET error: {exc!r}", file=sys.stderr)
                self._send(500, _failure("内部错误，请查看终端输出", 500)[1])

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if self._read_only_path(path):
                self._method_not_allowed()
                return
            if self.path not in {"/availability", "/record", "/advance"}:
                # sol 293 R2: unknown paths must not reach form parsing.
                self._send(404, _failure("页面不存在", 404)[1])
                return
            with _POST_LOCK:
                submitted = None
                try:
                    values = _read_form(self)
                    if "date" in values:
                        submitted = _parse_date(values["date"])
                    msg = _post_route(workspace, self.path, values, today_provider())
                    self.send_response(303)
                    self.send_header("Location", "/?msg=" + quote(msg))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                except RecordPipelineError as exc:
                    status, body = _failure_response(exc, submitted)
                    self._send(status, body)
                except (ValueError, ContractError) as exc:
                    self._send(400, _failure(str(exc))[1])
                except Exception as exc:
                    print(f"web POST error: {exc!r}", file=sys.stderr)
                    self._send(500, _failure("内部错误，请查看终端输出", 500)[1])

        def do_PUT(self) -> None:
            if self._read_only_path(urlsplit(self.path).path):
                self._method_not_allowed()
            else:
                self._send(404, _failure("页面不存在", 404)[1])

        def do_PATCH(self) -> None:
            self.do_PUT()

        def do_DELETE(self) -> None:
            self.do_PUT()

        def do_HEAD(self) -> None:
            if self._read_only_path(urlsplit(self.path).path):
                self._method_not_allowed()
            else:
                self._send(404, _failure("页面不存在", 404)[1])

        def do_OPTIONS(self) -> None:
            self.do_PUT()

        def do_TRACE(self) -> None:
            self.do_PUT()

        def do_CONNECT(self) -> None:
            self.do_PUT()

        def __getattr__(self, name: str):
            if name.startswith("do_"):
                return self._handle_other_method
            raise AttributeError(name)

        def _handle_other_method(self) -> None:
            if self._read_only_path(urlsplit(self.path).path):
                self._method_not_allowed()
            else:
                self._send(404, _failure("页面不存在", 404)[1])

        def log_message(self, fmt: str, *args) -> None:
            super().log_message(fmt, *args)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def _parse_date(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("expected YYYY-MM-DD")
    return parsed


def _parse_minutes(value: str) -> int:
    if not value or not value.isdecimal():
        raise ContractError("minutes must be an integer", "minutes")
    minutes = int(value)
    if minutes > 1440:
        raise ContractError("minutes must be from 0 to 1440", "minutes")
    return minutes


def _source_label(value: str) -> str:
    return {"availability": "手填", "timetable": "课表", "config": "配置",
            "base": "基数", "route": "路线", "pacing_initial": "复盘基数"}.get(value, value)
