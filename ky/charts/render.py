"""M17 Plotly rendering adapter; see ``contracts/charts.md`` §§2–4, 8.

Public interfaces: ``render_week`` and ``render_progress`` return deterministic
offline HTML pages. Data calculations stay in ``ky.charts.data``.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from html import escape
from typing import Any, Mapping

import plotly.graph_objects as go
import plotly.io as pio


_WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")
_LEVEL_LABELS = {
    "unlearned": "未学", "learned": "学过",
    "progressing": "掌握中", "consolidated": "已巩固",
}


def _page(title: str, note: str, cards: tuple[str, ...]) -> str:
    body = "\n".join(cards)
    return (
        "<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{escape(title)}</title><script src=\"plotly.min.js\"></script>"
        f"<style>{_styles()}</style></head><body><main><h1>{escape(title)}</h1>"
        f"<p class=\"page-note\">{escape(note)}</p>{body}</main>"
        f"{_theme_script()}</body></html>\n"
    )


def _styles() -> str:
    return """\
:root{color-scheme:light dark;--page:#f6f5f2;--card:#fcfcfb;--text:#0b0b0b;
--muted:#52514e;--weak:#8a8984;--grid:#e7e6e2;--off:#dcdbd6;--green:#1baf7a;
--subject-1:#2a78d6;--subject-2:#eb6834;--subject-3:#1baf7a;--subject-4:#eda100}
@media(prefers-color-scheme:dark){:root{--page:#121211;--card:#1a1a19;--text:#fff;
--muted:#c3c2b7;--weak:#8f8e86;--grid:#2c2c2a;--off:#3a3a37;--green:#199e70;
--subject-1:#3987e5;--subject-2:#d95926;--subject-3:#199e70;--subject-4:#c98500}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--text);
font:15px/1.55 system-ui,sans-serif}main{max-width:1180px;margin:0 auto;padding:30px 22px 48px}
h1{font-size:30px;margin:0 0 4px}.page-note{color:var(--muted);margin:0 0 22px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.card{min-width:0;background:var(--card);border-radius:16px;padding:20px 22px;
box-shadow:0 2px 14px #0000000b}.card h2{font-size:19px;margin:0}.caption{color:var(--muted);
font-size:13px;margin:3px 0 16px}.plot{width:100%;min-height:310px}
.coverage{grid-column:1/-1}
.tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:18px}
.tile{background:var(--page);border-radius:11px;padding:12px 14px}.tile-label{color:var(--muted);
font-size:12px}.tile-value{font-size:22px;font-variant-numeric:tabular-nums;font-weight:650;
white-space:nowrap}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:9px 7px;border-bottom:1px solid var(--grid)}
th{font-size:12px;color:var(--muted);font-weight:550;text-align:left}
.num{text-align:right;font-variant-numeric:tabular-nums}.attain{display:flex;align-items:center;
justify-content:flex-end;gap:8px;min-width:88px}
.bar{height:5px;width:46px;background:var(--off);border-radius:5px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--subject);border-radius:5px}
.tree-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.subject{min-width:0;border:1px solid var(--grid);border-radius:12px;padding:13px}
.subject-head{font-weight:650}.subject-count{color:var(--muted);font-size:12px}
.subject-progress{height:4px;background:var(--off);border-radius:4px;
margin:8px 0 10px;overflow:hidden}
.subject-progress i{display:block;height:100%;background:var(--subject)}
details{margin:2px 0 2px 10px}
summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:7px;min-height:28px}
summary::-webkit-details-marker{display:none}
summary::before{content:"\\25B8";color:var(--muted);font-size:11px;transition:transform .15s}
details[open]>summary::before{transform:rotate(90deg)}
.branch-title{flex:1;min-width:0;overflow-wrap:anywhere}
.branch-count{font-size:11px;color:var(--muted);white-space:nowrap}
.branch-bar{width:34px;height:4px;background:var(--off);border-radius:4px;overflow:hidden}
.branch-bar i{display:block;height:100%;background:var(--subject)}
.leaf{display:flex;gap:8px;align-items:center;margin:3px 0 3px 15px;overflow-wrap:anywhere}
.dot{color:var(--subject);font-size:13px}
.unlit{color:var(--weak)}.empty{color:var(--weak);padding:8px 0}
.week-card{margin-top:18px}.week-chart{width:100%;min-height:460px}
.ability-tree{grid-column:1/-1}.ability-subject{margin:10px 0;padding:12px;
border:1px solid var(--grid);border-radius:12px}.mastery-row{margin:12px 0}
.mastery-head{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.mastery-track{height:9px;background:var(--off);border-radius:8px;position:relative;
margin-top:7px;overflow:visible}.mastery-track i{display:block;height:100%;
background:var(--subject);border-radius:8px}.mastery-track b{position:absolute;top:-4px;width:2px;
height:17px;background:var(--text)}.critical{color:#c8443d;font-weight:650}.target-note{color:var(--muted)}
.tier-strip{display:flex;gap:2px;height:8px;border-radius:6px;overflow:hidden;min-width:42px}
.tier-strip i{display:block;min-width:0}.tier-learned{background:color-mix(in srgb,var(--subject) 35%,var(--card))}
.tier-unlearned{background:var(--off)}
.tier-progressing{background:color-mix(in srgb,var(--subject) 65%,var(--card))}
.tier-consolidated{background:var(--subject)}.level-dot{width:10px;height:10px;border-radius:50%;
display:inline-block;flex:none;border:1px solid var(--weak)}.level-learned{background:
color-mix(in srgb,var(--subject) 35%,var(--card));border-color:var(--subject)}
.level-progressing{background:color-mix(in srgb,var(--subject) 65%,var(--card));
border-color:var(--subject)}.level-consolidated{background:var(--subject);border-color:var(--subject)}
.weak-flag{color:#c8443d;font-size:12px;white-space:nowrap}.weak-table td{vertical-align:top}
.weak-table .level{white-space:nowrap}
.tier-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:15px;color:var(--muted);font-size:12px}
.tier-key{display:flex;align-items:center;gap:5px}.tier-key i{width:10px;height:8px;border-radius:2px}
@media(max-width:1100px){.grid{grid-template-columns:1fr}}
@media(max-width:820px){main{padding:22px 14px}.grid{grid-template-columns:1fr}
.tree-grid{grid-template-columns:1fr}.tiles{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""


def _theme_script() -> str:
    light = "#fcfcfb"
    return (
        "<script>(function(){const ids=Array.from(document.querySelectorAll('.plotly-graph-div'))"
        ".map(e=>e.id);const dark=window.matchMedia('(prefers-color-scheme: dark)');"
        "function update(){const night=dark.matches;const palette=night?"
        "['#3987e5','#d95926','#199e70','#c98500']:"
        "['#2a78d6','#eb6834','#1baf7a','#eda100'];const layout=night?"
        "{paper_bgcolor:'#1a1a19',plot_bgcolor:'#1a1a19',font:{color:'#ffffff'},"
        "'xaxis.gridcolor':'#2c2c2a','yaxis.gridcolor':'#2c2c2a'}:"
        "{paper_bgcolor:'#fcfcfb',plot_bgcolor:'#fcfcfb',font:{color:'#0b0b0b'},"
        "'xaxis.gridcolor':'#e7e6e2','yaxis.gridcolor':'#e7e6e2'};"
        "layout.colorway=palette;ids.forEach(id=>Plotly.relayout(id,layout));}"
        "dark.addEventListener('change',update);window.addEventListener('load',update);"
        "})();</script>"
    )


def _figure_html(figure: go.Figure, div_id: str) -> str:
    return pio.to_html(
        figure, full_html=False, include_plotlyjs=False, div_id=div_id,
        config={"displaylogo": False, "responsive": True},
    )


def _minute(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def render_week(data: Mapping[str, Any]) -> str:
    """Render a week calendar with course and free-time blocks."""
    figure = go.Figure()
    for index, day in enumerate(data["days"]):
        if not day["covered"]:
            figure.add_annotation(x=index, y=0, text="课表不覆盖", showarrow=False,
                                  yref="paper", yshift=-18)
            continue
        for start, end in day["free_segments"]:
            figure.add_shape(type="rect", x0=index - .34, x1=index + .34,
                             y0=_minute(start), y1=_minute(end),
                             fillcolor="rgba(27,175,122,.17)", line_width=0, layer="below")
        for course in day["classes"]:
            first, last = course["first_period"], course["last_period"]
            figure.add_shape(type="rect", x0=index - .29, x1=index + .29,
                             y0=_minute(course["start"]), y1=_minute(course["end"]),
                             fillcolor=_LIGHT[0], line={"color": _LIGHT[0],
                             "dash": "dash" if course["unconfirmed"] else "solid", "width": 2})
            figure.add_annotation(
                x=index, y=(_minute(course["start"]) + _minute(course["end"])) / 2,
                text=f"{escape(course['name'][:8])}<br>{first}–{last} 节", showarrow=False,
                font={"color": "white", "size": 11},
                hovertext=(f"{escape(course['name'])}<br>{course['start']}–{course['end']}<br>"
                           f"第 {first}–{last} 节<br>待确认：{'是' if course['unconfirmed'] else '否'}"),
            )
    low, high = (_minute(data["time_range"][0]), _minute(data["time_range"][1]))
    labels = []
    for name, day in zip(_WEEKDAYS, data["days"]):
        stamp = day["date"][5:].replace("-", "/")
        available = "—" if day["minutes"] is None else f"可学 {day['minutes']} 分"
        labels.append(f"{name} {stamp}<br>{available}")
    figure.update_layout(
        height=480, margin={"t": 65, "b": 42, "l": 54, "r": 16},
        xaxis={"tickmode": "array", "tickvals": list(range(7)), "ticktext": labels,
               "range": [-.5, 6.5], "side": "top", "fixedrange": True,
               "gridcolor": "#e7e6e2"},
        yaxis={"range": [high, low], "tickmode": "array",
               "tickvals": list(range(low // 60 * 60, high + 1, 60)),
               "ticktext": [f"{minute // 60:02d}:00"
                            for minute in range(low // 60 * 60, high + 1, 60)],
               "gridcolor": "#e7e6e2"},
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb", font={"color": "#0b0b0b"},
        showlegend=False, hoverlabel={"align": "left"},
    )
    title = f"{data['semester']} 第 {data['week']} 周课表"
    card = ("<section class=\"card week-card\"><h2>一周课表</h2>"
            "<p class=\"caption\">课程时段只作展示；实际可学时间以浅绿空闲时段为准。</p>"
            f"{_figure_html(figure, 'chart-week-0')}</section>")
    return _page(title, "课程安排与每日可学时间。", (card,))


def _percent(value: int, total: int, places: int = 0) -> str:
    if total == 0:
        return "—"
    quantum = Decimal("1") if places == 0 else Decimal("0.1")
    return str((Decimal(value * 100) / Decimal(total)).quantize(
        quantum, rounding=ROUND_HALF_EVEN,
    ))


def _date_label(value: str) -> str:
    day = value[5:].split("-")
    return f"{int(day[0])}/{int(day[1])}"


def _daily_card(data: Mapping[str, Any]) -> str:
    totals = data["daily_totals"]
    days = data["daily"]
    interval = len(days)
    recorded = totals["recorded_days"]
    actual_sum = totals["actual_sum"]
    reference_sum = totals["reference_sum_on_recorded_days"]
    attainment = _percent(actual_sum, reference_sum) if recorded and reference_sum else "—"
    tiles = (
        ("有记录天数", f"{recorded} / {interval}"), ("实际合计", f"{actual_sum} 分钟"),
        ("同日参考合计", f"{reference_sum} 分钟"), ("达成率", "—" if attainment == "—"
                                                    else f"{attainment}%"),
    )
    tile_html = "".join(
        f"<div class=\"tile\"><div class=\"tile-label\">{label}</div>"
        f"<div class=\"tile-value\">{value}</div></div>" for label, value in tiles
    )
    rows = []
    for row in reversed(days):
        actual = row["actual"]
        if actual is None:
            actual_text, progress = "未记录", "—"
        elif row["reference"] == 0:
            actual_text, progress = str(actual), "—"
        else:
            percent = _percent(actual, row["reference"], 1)
            width = min(100, max(0, actual * 100 / row["reference"]))
            color = "var(--subject-1)"
            progress = (f"<span class=\"attain\"><span class=\"bar\"><i "
                        f"style=\"width:{width:.1f}%;--subject:{color}\"></i></span>"
                        f"{percent}%</span>")
            actual_text = str(actual)
        weekday = _WEEKDAYS[(date_from_iso(row["date"]).isoweekday() - 1)]
        rows.append(
            f"<tr><td>{_date_label(row['date'])}</td><td>{weekday}</td>"
            f"<td class=\"num\">{actual_text}</td><td class=\"num\">{row['reference']}</td>"
            f"<td class=\"num\">{progress}</td></tr>"
        )
    return ("<section class=\"card\"><h2>每日学习分钟</h2>"
            "<p class=\"caption\">参考分钟按生成时来源重算。</p>"
            f"<div class=\"tiles\">{tile_html}</div><table><thead><tr>"
            "<th>日期</th><th>星期</th><th class=\"num\">实际</th>"
            "<th class=\"num\">参考</th><th class=\"num\">达成</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table></section>")


def date_from_iso(value: str):
    from datetime import date
    return date.fromisoformat(value)


def _weekly_figure(data: Mapping[str, Any], subjects: tuple[str, ...],
                   names: Mapping[str, str]) -> go.Figure:
    rows = data["weekly_plan"]
    figure = go.Figure()
    for index, subject in enumerate(subjects):
        figure.add_trace(go.Bar(
            x=[row["week_start"] for row in rows],
            y=[row["minutes"][subject] for row in rows], name=names[subject],
            marker_color=_LIGHT[index % len(_LIGHT)],
            customdata=[[row["from"], row["to"]] for row in rows],
            hovertemplate="%{customdata[0]} 至 %{customdata[1]}<br>%{y} 分钟<extra></extra>",
        ))
    figure.update_layout(
        barmode="stack", height=330, margin={"t": 20, "b": 55, "l": 48, "r": 16},
        xaxis={"tickmode": "array", "tickvals": [row["week_start"] for row in rows],
               "ticktext": [f"{row['from']}–{row['to']}" for row in rows],
               "gridcolor": "#e7e6e2"}, yaxis={"title": "计划分钟", "gridcolor": "#e7e6e2"},
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb", font={"color": "#0b0b0b"},
        legend={"orientation": "h", "y": 1.18, "x": 0},
    )
    return figure


def _tree_node(node: Mapping[str, Any], color: str, *, open_node: bool) -> str:
    if not node["children"]:
        lit = node["lit"] > 0
        symbol = "●" if lit else "○"
        klass = "leaf" if lit else "leaf unlit"
        return (f"<div class=\"{klass}\"><span class=\"dot\" style=\"--subject:{color}\">"
                f"{symbol}</span><span>{escape(node['title'])}</span></div>")
    width = 0 if node["leaves"] == 0 else node["lit"] * 100 / node["leaves"]
    children = "".join(_tree_node(child, color, open_node=False)
                       for child in node["children"])
    opened = " open" if open_node else ""
    return (
        f"<details{opened}><summary><span class=\"branch-title\">{escape(node['title'])}</span>"
        f"<span class=\"branch-bar\"><i style=\"width:{width:.1f}%;--subject:{color}\"></i></span>"
        f"<span class=\"branch-count\">{node['lit']}/{node['leaves']}</span></summary>"
        f"{children}</details>"
    )


def _coverage_card(data: Mapping[str, Any]) -> str:
    columns = []
    for index, row in enumerate(data["coverage"]):
        color = f"var(--subject-{index % len(_LIGHT) + 1})"
        if row["tree"] is None:
            content = "<div class=\"empty\">无知识树</div>"
            count = "— / —"
            width = 0
        else:
            total, covered = row["total"], row["covered"]
            percent = _percent(covered, total, 1) if total else "0.0"
            count = f"{covered} / {total}（{percent}%）"
            width = covered * 100 / total if total else 0
            content = "".join(_tree_node(node, color, open_node=True)
                              for node in row["tree"]["children"])
        columns.append(
            f"<div class=\"subject\" style=\"--subject:{color}\"><div class=\"subject-head\">"
            f"{escape(row['name'])}</div><div class=\"subject-count\">点亮 / 总数：{count}</div>"
            f"<div class=\"subject-progress\"><i style=\"width:{width:.1f}%\"></i></div>"
            f"{content}</div>"
        )
    return ("<section class=\"card coverage\"><h2>知识树完成度</h2>"
            "<p class=\"caption\">按当前复习队列的引用折算“学过一遍”的覆盖，不是掌握度。</p>"
            f"<div class=\"tree-grid\">{''.join(columns)}</div></section>")


def _route_figure(data: Mapping[str, Any], subject_names: Mapping[str, str]) -> go.Figure:
    route = data["route"]
    figure = go.Figure()
    if route is None:
        figure.add_annotation(text="尚无路线", x=.5, y=.5, xref="paper", yref="paper",
                              showarrow=False)
    else:
        for phase in route["phases"]:
            review = "、".join(
                f"{subject_names.get(subject, '其他科目')} {minutes} 分钟"
                for subject, minutes in phase["review_minutes"].items()
            )
            hover = (f"{escape(phase['label'])}<br>基础分钟：{phase['base_daily_minutes']}<br>"
                     f"各科复习分钟：{escape(review)}")
            figure.add_trace(go.Scatter(
                x=[phase["start"], phase["end_exclusive"]], y=[phase["label"]] * 2,
                mode="lines", line={"width": 22, "color": _LIGHT[0]},
                text=[hover, hover], hovertemplate="%{text}<extra></extra>", showlegend=False,
            ))
        figure.add_vline(x=data["today"], line_dash="dash", annotation_text="今天")
    figure.update_layout(
        height=300, margin={"t": 18, "b": 46, "l": 54, "r": 14},
        xaxis={"title": "日期", "gridcolor": "#e7e6e2"},
        yaxis={"title": "阶段", "gridcolor": "#e7e6e2"},
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb", font={"color": "#0b0b0b"},
        title=("阶段推进" if route is None else
               f"阶段推进（距考试 {route['days_to_exam']} 天）"),
    )
    return figure


_ABILITY_NOTE = (
    "档位由 FSRS 记忆稳定度（尚未用 FSRS 核对过的项用阶梯间隔）决定，"
    "只随有锚点的核对变化，自评不参与。"
)


def _percentage(value: str | None) -> str:
    if value is None:
        return "—"
    percent = (Decimal(value) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
    return f"{percent:.1f}%"


def _share_width(value: str | None) -> float:
    return 0.0 if value is None else float(Decimal(value) * 100)


def _ability_card(data: Mapping[str, Any]) -> str:
    rows = []
    for index, subject in enumerate(data["subjects"]):
        color = f"var(--subject-{index % len(_LIGHT) + 1})"
        shares = subject["shares"]
        if shares is None:
            strip = "<div class=\"empty\">无可用权重</div>"
        else:
            segments = []
            for level, style in (("unlearned", "tier-unlearned"),
                                 ("learned", "tier-learned"),
                                 ("progressing", "tier-progressing"),
                                 ("consolidated", "tier-consolidated")):
                width = _share_width(shares[level])
                segments.append(
                    f"<i class=\"{style}\" "
                    f"title=\"{_LEVEL_LABELS[level]} {_percentage(shares[level])}\" "
                    f"style=\"width:{width:.4f}%\"></i>"
                )
            strip = f"<div class=\"tier-strip\" style=\"--subject:{color}\">"
            strip += "".join(segments) + "</div>"
        note = ""
        if subject["weighted"]:
            count = len(subject["unweighted_leaves"])
            note = (f"<div class=\"caption\">按近年真题考频加权；{count} 个知识点近年未考 "
                    "（权重 0）</div>")
        rows.append(
            f"<div class=\"mastery-row\" style=\"--subject:{color}\"><div "
            f"class=\"mastery-head\"><strong>{escape(subject['name'])}</strong>"
            f"<span>能力 {_percentage(subject['ability'])}</span></div>{strip}{note}</div>"
        )
    legend = "".join(
        f"<span class=\"tier-key\"><i class=\"{style}\" style=\"--subject:"
        f"var(--subject-1)\"></i>{_LEVEL_LABELS[level]}</span>"
        for level, style in (("unlearned", "tier-unlearned"),
                             ("learned", "tier-learned"),
                             ("progressing", "tier-progressing"),
                             ("consolidated", "tier-consolidated"))
    )
    return ("<section class=\"card\"><h2>四科能力</h2>"
            f"{''.join(rows)}"
            f"<div class=\"tier-legend\">{legend}</div></section>")


def _gap_metric(
    label: str, current: str | None, expected: str, gap: str | None, color: str,
) -> str:
    lag = gap is not None and gap.startswith("-")
    text = f"{label} 当前 {_percentage(current)} / 应到 {_percentage(expected)}"
    if lag:
        text += " 落后"
    klass = "critical" if lag else ""
    marker = f"<b style=\"left:{_share_width(expected):.4f}%\"></b>"
    return (
        f"<div class=\"mastery-metric\" style=\"--subject:{color}\"><div "
        f"class=\"mastery-head\"><span class=\"{klass}\">{text}</span></div>"
        f"<div class=\"mastery-track\"><i style=\"width:{_share_width(current):.4f}%\"></i>"
        f"{marker}</div></div>"
    )


def _gap_card(data: Mapping[str, Any]) -> str:
    status = data["status"]
    if status == "missing_route":
        body = "<div class=\"empty\">目标差距需要路线</div>"
    elif status == "no_targets":
        body = "<div class=\"empty\">路线还没写阶段目标</div>"
    else:
        rows = []
        expected = data["expected"]
        for index, subject in enumerate(data["subjects"]):
            color = f"var(--subject-{index % len(_LIGHT) + 1})"
            coverage = _gap_metric(
                "覆盖", subject["covered"], expected["covered"],
                subject["gap_covered"], color,
            )
            consolidation = _gap_metric(
                "巩固", subject["ability"], expected["consolidated"],
                subject["gap_consolidated"], color,
            )
            rows.append(
                f"<div class=\"mastery-row\"><strong>{escape(subject['name'])}</strong>"
                f"{coverage}{consolidation}</div>"
            )
        body = "".join(rows)
    return ("<section class=\"card\"><h2>阶段目标差距</h2>"
            f"<p class=\"caption\">覆盖与巩固目标按路线阶段末目标逐日插值。</p>"
            f"{body}</section>")


def _tier_strip(counts: Mapping[str, int], leaves: int, color: str) -> str:
    if leaves == 0:
        return ""
    parts = []
    for level, style in (("unlearned", "tier-unlearned"), ("learned", "tier-learned"),
                         ("progressing", "tier-progressing"),
                         ("consolidated", "tier-consolidated")):
        width = counts[level] * 100 / leaves
        parts.append(f"<i class=\"{style}\" style=\"width:{width:.4f}%\"></i>")
    return f"<span class=\"tier-strip\" style=\"--subject:{color}\">{''.join(parts)}</span>"


def _ability_tree_node(
    node: Mapping[str, Any], color: str, *, open_node: bool,
) -> str:
    if not node["children"]:
        level = node["level"]
        flag = " <span class=\"weak-flag\">⚠ 遗忘 ≥2</span>" if node["weak"] else ""
        return (
            f"<div class=\"leaf\"><span class=\"level-dot level-{level}\" "
            f"style=\"--subject:{color}\"></span><span>{escape(node['title'])}{flag}</span></div>"
        )
    children = "".join(
        _ability_tree_node(child, color, open_node=False) for child in node["children"]
    )
    opened = " open" if open_node else ""
    strip = _tier_strip(node["counts"], node["leaves"], color)
    consolidated = node["counts"]["consolidated"]
    return (
        f"<details{opened}><summary><span class=\"branch-title\">{escape(node['title'])}</span>"
        f"{strip}<span class=\"branch-count\">{consolidated}/{node['leaves']}</span>"
        f"</summary>{children}</details>"
    )


def _ability_tree_card(data: Mapping[str, Any]) -> str:
    columns = []
    for index, subject in enumerate(data["subjects"]):
        color = f"var(--subject-{index % len(_LIGHT) + 1})"
        tree = subject["tree"]
        if tree is None:
            children = "<div class=\"empty\">无知识树</div>"
        else:
            children = "".join(
                _ability_tree_node(node, color, open_node=True)
                for node in tree["children"]
            )
        columns.append(
            f"<div class=\"subject\" style=\"--subject:{color}\"><div "
            f"class=\"subject-head\">{escape(subject['name'])}</div>{children}</div>"
        )
    return ("<section class=\"card ability-tree\"><h2>各模块掌握度</h2>"
            "<p class=\"caption\">每章右侧是四档分布与 已巩固 / 知识点数。</p><div class=\"tree-grid\">"
            f"{''.join(columns)}</div></section>")


def _weak_card(data: Mapping[str, Any]) -> str:
    weak = data["weak_items"]
    if not weak:
        body = "<div class=\"empty\">暂无薄弱点（遗忘 ≥ 2 次的知识点）</div>"
    else:
        rows = "".join(
            f"<tr><td>{escape(row['subject_name'])}</td><td>{escape(row['chapter'])}</td>"
            f"<td>{escape(row['title'])}</td><td class=\"num\">{row['lapses']}</td>"
            f"<td class=\"level\">{_LEVEL_LABELS[row['level']]}</td></tr>"
            for row in weak
        )
        body = ("<table class=\"weak-table\"><thead><tr><th>科目</th><th>所在章</th>"
                "<th>知识点</th><th class=\"num\">遗忘次数</th><th>当前档位</th>"
                f"</tr></thead><tbody>{rows}</tbody></table>")
    return ("<section class=\"card\"><h2>薄弱点清单</h2>"
            "<p class=\"caption\">遗忘 ≥ 2 次的知识点；遗忘次数取该知识点所挂复习项中的最大值。</p>"
            f"{body}</section>")


def render_ability(data: Mapping[str, Any]) -> str:
    """Render M30 mastery, target-gap, tree, and weakness cards."""
    cards = (_ability_card(data), _gap_card(data), _ability_tree_card(data), _weak_card(data))
    return _page(f"能力画像 · {data['today']}", _ABILITY_NOTE,
                 ("<div class=\"grid\">" + "".join(cards) + "</div>",))


def _plot_card(title: str, caption: str, figure: go.Figure, div_id: str) -> str:
    return (f"<section class=\"card\"><h2>{escape(title)}</h2>"
            f"<p class=\"caption\">{escape(caption)}</p>"
            f"{_figure_html(figure, div_id)}</section>")


def render_progress(data: Mapping[str, Any], subjects: tuple[str, ...],
                    subject_names: Mapping[str, str]) -> str:
    """Render daily, weekly, coverage, and route cards in contract order."""
    weekly = ("<section class=\"card\"><h2>四科计划分钟（按周）</h2>"
              "<p class=\"caption\">只含知识点通道的分科计划分钟，不含单词 / 短语通道。</p>"
              "<div class=\"empty\">区间内没有日计划</div></section>"
              if not data["weekly_plan"] else
              _plot_card("四科计划分钟（按周）",
                         "只含知识点通道的分科计划分钟，不含单词 / 短语通道。",
                         _weekly_figure(data, subjects, subject_names), "chart-progress-0"))
    route = data["route"]
    route_note = "阶段与考试日期。" if route is None else f"距目标考试日期 {route['days_to_exam']} 天。"
    cards = (
        _daily_card(data), weekly, _coverage_card(data),
        _plot_card("阶段推进", route_note, _route_figure(data, subject_names),
                   "chart-progress-1"),
    )
    note = (f"数据区间：{data['from']} 至 {data['to']}。参考分钟按生成时来源重算；"
            "图表按配置顺序显示科目名称。")
    return _page("学习进度", note, ("<div class=\"grid\">" +
                                      "".join(cards) + "</div>",))
