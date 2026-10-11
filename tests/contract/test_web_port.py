from __future__ import annotations

import tempfile
import threading
import unittest
import contextlib
import io
import socket
import http.client
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from urllib.parse import quote, urlencode

import yaml

from ky.web.server import _render, _render_queue, _render_route, make_server
from ky.models import ContractError
from ky.today.record import RecordPipelineError
from ky.schedule.completion import CompletionEvent, ReviewCompletion
from ky.schedule.planning import Phase, RoutePlan
from ky.storage.day_plan_store import DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.web.cli import web_main
from ky.workspace import WORKSPACE_FILENAME, load_workspace

ROOT = Path(__file__).resolve().parents[2]


def _workspace(root: Path, *, availability: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "config.yaml"
    config_path.write_bytes((ROOT / "tests/fixtures/config/config-minimal.yaml").read_bytes())
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    subjects = {item["subject_id"]: {"name": item["display_name"]}
                for item in config["subjects"]}
    registry = {
        "schema_version": 2, "subjects": subjects,
        "reference": {"knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                      "topic_weights": "data/weights.json", "weight_batches": "data/batches.yaml",
                      "vocabulary_db": "data/vocab.sqlite", "ledger": "data/ledger.yaml"},
        "supplementary": {}, "materials": {"raw_root": "data/raw"}, "products": {},
        "settings": {"exam_config": "config.yaml"},
        "state": {"review_queue": "state/review_queue", "plans": "state/plans"},
        "staging": "staging", "projection": "data/projection.sqlite",
    }
    if availability:
        registry["state"]["availability"] = "state/availability.yaml"
        availability_path = root / "state/availability.yaml"
        availability_path.parent.mkdir(parents=True, exist_ok=True)
        availability_path.write_text("schema_version: 1\ndays: {}\n", encoding="utf-8")
    path = root / WORKSPACE_FILENAME
    path.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


class WebPortContractTests(unittest.TestCase):
    def test_queue_render_freeze_order_bucket_fields_split_and_tiers(self) -> None:
        # sol 293 R1: verify visible order, all bucket columns, and Chinese tiers.
        day = "2026-10-08"
        buckets = {
            "selected": {"count": 1, "minutes": 5},
            "deferred": {"count": 2, "minutes": 6},
            "unschedulable": {"count": 1, "minutes": 30},
            "scheduled_ahead": {"count": 3, "minutes": 9},
            "unreachable": {"count": 4, "minutes": 12},
        }
        selected = [
            {"review_id": f"r{index}", "knowledge_point_id": "math1.topic",
             "title": "合成项", "subject_name": "数学一", "level": level,
             "due_date": "2026-10-01", "overdue_days": 7, "defer_count": 0,
             "lapses": 0, "estimated_minutes": 5}
            for index, level in enumerate(("learned", "progressing", "consolidated"))
        ]
        view = {
            "date": day, "freeze": {"overdue_minutes": 50,
                                     "threshold_minutes": 40},
            "budget": {"total_minutes": 5, "total_source": "config",
                       "base_minutes": 5, "base_source": "config"},
            "caps": {"soft_target_minutes": 1, "hard_cap_minutes": 1},
            "buckets": buckets, "selected": selected,
            "backlog": {"count": 7, "minutes": 48, "by_subject": {},
                        "details": [], "remaining_count": 0},
            "ahead": {"count": 0, "due_dates": []},
        }
        _status, body = _render_queue(view)
        rendered = body.decode("utf-8")
        self.assertLess(rendered.index("<h2>复习冻结"), rendered.index("<h1>"))
        self.assertLess(rendered.index("<h1>"), rendered.index("<h2>今天的时间"))
        for label, count, minutes in (
            ("今天入选", 1, 5), ("延期", 2, 6), ("单项太大", 1, 30),
            ("未到期", 3, 9), ("过期但不可选", 4, 12),
        ):
            self.assertIn(f"{label}：{count} 项，{minutes} 分钟", rendered)
        self.assertIn("单项太大，请拆分", rendered)
        for tier in ("学过", "掌握中", "已巩固"):
            self.assertIn(tier, rendered)
        for tier in ("learned", "progressing", "consolidated"):
            self.assertNotIn(tier, rendered)

    def test_missing_review_queue_registration_fails_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry_path = _workspace(Path(temporary))
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            del registry["state"]["review_queue"]
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                result = web_main([
                    "--port", "0", "--no-open", "--workspace", str(registry_path),
                ])
        self.assertEqual(result, 2)
        self.assertIn("state.review_queue", errors.getvalue())
        missing = Path(temporary) / "missing" / WORKSPACE_FILENAME
        with contextlib.redirect_stderr(errors):
            result = web_main([
                "--port", "0", "--no-open", "--workspace", str(missing),
            ])
        self.assertEqual(result, 2)

    def test_route_page_shows_current_phase_and_latest_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_path = _workspace(root)
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            registry["state"]["routes"] = "state/routes"
            registry["settings"]["pacing"] = "settings/pacing.yaml"
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            pacing_path = root / "settings/pacing.yaml"
            pacing_path.parent.mkdir(parents=True)
            pacing_path.write_text("schema_version: 1\n", encoding="utf-8")
            workspace = load_workspace(registry_path)
            day = date(2026, 10, 8)
            route = RoutePlan(
                "route-test", 3, date(2026, 10, 1), date(2026, 10, 20), "v1",
                "a" * 64,
                (Phase(0, date(2026, 10, 1), date(2026, 10, 12), "当前阶段",
                       {"math1": 30}, targets={"covered": 8, "consolidated": 3}),
                 Phase(1, date(2026, 10, 12), date(2026, 10, 20), "后续阶段",
                       {"math1": 25}, targets={"covered": 10, "consolidated": 5})),
            )
            cycle = type("Cycle", (), {
                "start": date(2026, 10, 1), "end": date(2026, 10, 15),
            })()
            saved = {
                "2026-09-15": {"base": {"min": 110, "max": 160, "mean": 130},
                               "reviews": {}},
                "2026-09-30": {"base": {"min": 120, "max": 180, "mean": 150},
                               "reviews": {"math1": {"completed": 4, "correct": 3,
                                "partial": 1, "incorrect": 0,
                                "none": 0}}},
            }
            before = _tree_bytes(root)
            with patch("ky.web.server.RoutePlanStore.current", return_value=route) as current, \
                 patch("ky.web.server.settings_for_workspace", return_value=object()) as settings, \
                 patch("ky.web.server.daily_base_minutes", return_value=(175, "route")), \
                 patch("ky.web.server.cycle_for_date", return_value=cycle), \
                 patch("ky.web.server.load_pacing_report_state",
                       return_value=((cycle,), saved)) as reports:
                _status, body = _render_route(workspace, day)
            self.assertEqual(current.call_count, 1)
            self.assertEqual(settings.call_count, 1)
            self.assertEqual(reports.call_count, 1)
            self.assertEqual(_tree_bytes(root), before)

        rendered = body.decode("utf-8")
        self.assertIn("route-test", rendered)
        self.assertIn("aaaaaaaaaaaa", rendered)
        self.assertIn("aria-current='step'", rendered)
        self.assertNotIn("未设目标", rendered)
        self.assertIn("未报告周期：2026-10-15", rendered)
        self.assertIn("最近报告：2026-09-30", rendered)
        self.assertIn("120 / 180 / 150", rendered)
        self.assertIn("completed 4", rendered)

    def test_registered_empty_route_and_future_cycle_render_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_path = _workspace(root)
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            registry["state"]["routes"] = "state/routes"
            registry["settings"]["pacing"] = "settings/pacing.yaml"
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            pacing_path = root / "settings/pacing.yaml"
            pacing_path.parent.mkdir()
            pacing_path.write_text("schema_version: 1\n", encoding="utf-8")
            workspace = load_workspace(registry_path)
            before = _tree_bytes(root)
            server = make_server(workspace, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch("ky.web.server.settings_for_workspace", return_value=object()), \
                     patch("ky.web.server.daily_base_minutes",
                           return_value=(90, "config")), \
                     patch("ky.web.server.cycle_for_date", return_value=None), \
                     patch("ky.web.server.load_pacing_report_state",
                           return_value=((), {})) as reports:
                    with urlopen(
                        f"http://127.0.0.1:{server.server_port}/route?date=2026-10-08"
                    ) as response:
                        self.assertEqual(response.status, 200)
                        rendered = response.read().decode("utf-8")
                self.assertIn("还没有路线", rendered)
                self.assertIn("复盘尚未开始；下个复盘日：空", rendered)
                self.assertEqual(reports.call_count, 1)
                self.assertEqual(_tree_bytes(root), before)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_queue_endpoint_renders_nonempty_frozen_view_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = load_workspace(_workspace(root))
            item = yaml.safe_load(
                (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_text(
                    encoding="utf-8",
                )
            )["items"][0]
            item["due_date"] = "2026-10-01"
            ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
            DayPlanStore(workspace.write_target("state.plans")).write_freeze_record(
                date(2026, 10, 8), {"latched": True},
            )
            before = _tree_bytes(root)
            server = make_server(workspace, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/queue?date=2026-10-08"
                ) as response:
                    self.assertEqual(response.status, 200)
                    rendered = response.read().decode("utf-8")
                self.assertLess(rendered.index("<h2>复习冻结"), rendered.index("<h1>"))
                self.assertIn(item["review_id"], rendered)
                self.assertIn(item["title"], rendered)
                self.assertIn("学过", rendered)
                self.assertEqual(_tree_bytes(root), before)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_unregistered_charts_show_prompt_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = load_workspace(_workspace(root))
            before = _tree_bytes(root)
            server = make_server(workspace, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/charts") as response:
                    self.assertEqual(response.status, 200)
                    rendered = response.read().decode("utf-8")
                self.assertIn("未登记图表目录，请让 AI 检查注册表", rendered)
                self.assertEqual(_tree_bytes(root), before)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def _http_request(self, base, method, path):
        request = Request(base + path, data=b"" if method == "POST" else None,
                          method=method)
        try:
            with urlopen(request) as response:
                return response.status, response.headers, response.read()
        except HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def _assert_chart_resources(self, request, charts, html_bytes, js_bytes,
                                encoded_name):
        html_response = request("GET", "/charts/week--sample.html")
        js_response = request("GET", "/charts/plotly.min.js")
        charts_page = request("GET", "/charts")
        self.assertIn(b"plotly.min.js", html_response[2])
        self.assertEqual(html_response[1].get_content_type(), "text/html")
        self.assertEqual(html_response[1]["Content-Length"], str(len(html_bytes)))
        self.assertEqual(html_response[2], html_bytes)
        self.assertEqual(js_response[1].get_content_type(), "application/javascript")
        self.assertEqual(js_response[1]["Content-Length"], str(len(js_bytes)))
        self.assertEqual(js_response[2], js_bytes)
        self.assertIn(quote(encoded_name).encode("ascii"), charts_page[2])
        self.assertNotIn(b"plotly.min.js</a>", charts_page[2])

    def _assert_chart_fallbacks(self, request, root, charts, js_bytes, encoded_name):
        script_path = charts / "plotly.min.js"
        script_path.unlink()
        self.assertIn("图表脚本缺失".encode("utf-8"), request("GET", "/charts")[2])
        script_path.write_bytes(js_bytes)
        html_path = charts / "week--sample.html"
        hidden_html = charts / "week--sample.disabled"
        encoded_path = charts / encoded_name
        hidden_encoded = charts / "week--encoded.disabled"
        html_path.rename(hidden_html)
        encoded_path.rename(hidden_encoded)
        self.assertIn(b"ky chart week", request("GET", "/charts")[2])
        hidden_html.rename(html_path)
        hidden_encoded.rename(encoded_path)
        hidden_charts = root / "products/charts-disabled"
        charts.rename(hidden_charts)
        self.assertIn(b"ky chart week", request("GET", "/charts")[2])
        hidden_charts.rename(charts)

    def _assert_readonly_rejections(self, request, server, root):
        self.assertEqual(request("GET", "/charts/%2e%2e%2fsecret.html")[0], 404)
        self.assertEqual(request("GET", "/charts/week--missing.html")[0], 404)
        self.assertEqual(request("GET", "/charts?unexpected=1")[0], 400)
        invalid_paths = (
            "/queue?date=not-a-date", "/route?date=not-a-date",
            "/queue?date=2026-10-08&date=2026-10-09",
            "/route?date=2026-10-08&date=2026-10-09",
        )
        for path in invalid_paths:
            self.assertEqual(request("GET", path)[0], 400)
        error = ContractError("registered source is invalid", "state")
        with patch("ky.web.server.load_queue_view", side_effect=error):
            self.assertEqual(request("GET", "/queue?date=2026-10-08")[0], 400)
        self.assertEqual(request("GET", "/unknown")[0], 404)
        before = _tree_bytes(root)
        methods = (
            ("POST", "/queue"), ("PUT", "/route"), ("DELETE", "/charts"),
            ("PATCH", "/charts/week--sample.html"),
            ("DELETE", "/charts/plotly.min.js"),
        )
        for method, path in methods:
            status, headers, _body = request(method, path)
            self.assertEqual(status, 405)
            self.assertEqual(headers.get("Allow"), "GET")
        self.assertEqual(_tree_bytes(root), before)
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5,
        )
        connection.request("POST", "/unknown", body=b"")
        response = connection.getresponse()
        self.assertEqual(response.status, 404)
        response.read()
        connection.close()

    def test_readonly_pages_resources_methods_and_workspace_tree(self) -> None:
        # sol 293 R3: keep method, query, file-tree, and encoded-resource branches testable.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_path = _workspace(root)
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            registry["products"]["charts"] = "products/charts"
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            charts = root / "products/charts"
            charts.mkdir(parents=True)
            html_bytes = b"<script src='plotly.min.js'></script><h1>offline</h1>"
            js_bytes = b"window.Plotly={};"
            (charts / "week--sample.html").write_bytes(html_bytes)
            (charts / "plotly.min.js").write_bytes(js_bytes)
            encoded_name = "week--复习.html"
            (charts / encoded_name).write_bytes(b"<h1>encoded</h1>")
            workspace = load_workspace(registry_path)
            before = _tree_bytes(root)
            server = make_server(workspace, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            request = lambda method, path: self._http_request(base, method, path)
            try:
                queue = request("GET", "/queue?date=2026-10-08")
                route = request("GET", "/route?date=2026-10-08")
                charts_page = request("GET", "/charts")
                self.assertEqual(queue[0], 200)
                self.assertIn("复习队列是空的", queue[2].decode("utf-8"))
                self.assertIn("今天", queue[2].decode("utf-8"))
                self.assertEqual(route[0], 200)
                self.assertIn("还没有路线", route[2].decode("utf-8"))
                self.assertIn("未登记复盘设置", route[2].decode("utf-8"))
                self.assertEqual(charts_page[0], 200)
                self._assert_chart_resources(
                    request, charts, html_bytes, js_bytes, encoded_name,
                )
                self._assert_chart_fallbacks(
                    request, root, charts, js_bytes, encoded_name,
                )
                self._assert_readonly_rejections(request, server, root)
                self.assertEqual(_tree_bytes(root), before)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_pending_record_renders_saved_results_and_zero_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = load_workspace(_workspace(Path(temporary)))
            queue_items = yaml.safe_load(
                (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_text(
                    encoding="utf-8"
                )
            )["items"]
            item = queue_items[0]
            ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
            day = date(2026, 10, 2)
            plans = DayPlanStore(workspace.write_target("state.plans"))
            plans.write_completion_event(CompletionEvent(
                day, (ReviewCompletion(
                    item["review_id"], day, "recall_vs_notes", "correct",
                ),), study_minutes=0,
            ))
            saved = plans.read_state_sources().completions[0]
            view = {
                "date": day.isoformat(),
                "budget": {"total_minutes": 0, "total_source": "config",
                           "base_minutes": 0, "base_source": "config"},
                "preflight": {}, "reviews": [], "route_phase": None,
                "timetable": None,
                "recorded": {
                    "advanced": False,
                    "study_minutes": saved.study_minutes,
                    "reviews": [{"review_id": result.review_id,
                                 "outcome": result.outcome}
                                for result in saved.reviews],
                },
                "availability_registered": False, "pacing": None,
                "view_hash": "0" * 64,
            }
            _, body = _render(view, day)
            rendered = body.decode("utf-8")

            self.assertIn("已记录，复习队列未推进", rendered)
            self.assertIn("补推进复习队列", rendered)
            self.assertIn("学习分钟：0 分钟", rendered)
            self.assertIn(item["review_id"] + "：对", rendered)

    def test_threaded_local_server_uses_ephemeral_port_and_serves_today(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = load_workspace(_workspace(Path(temporary)))
            server = make_server(workspace, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                self.assertEqual(server.server_address[0], "127.0.0.1")
                with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
                    body = response.read().decode("utf-8")
                self.assertIn(date.today().isoformat(), body)
                self.assertIn("今天的复习", body)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
            self.assertFalse(thread.is_alive())

    def test_dynamic_review_text_is_html_escaped(self) -> None:
        view = {
            "date": "2026-10-02", "budget": {"total_minutes": 60,
                "total_source": "config", "base_minutes": 60, "base_source": "config"},
            "preflight": {
                "selected": [{"review_id": "r", "subject_id": "math1"}],
                "subject_allocation": [{"subject_id": "math1", "display_name": "数学一"}],
            },
            "reviews": [
                {"review_id": "r", "title": "<script>&", "level": "learned",
                 "question_level": "adapted", "check": "exercise",
                 "question": {"stem": "x<0", "choices": ["A. <x&"],
                              "answer": "<script>"}},
                {"review_id": "missing", "title": "缺题", "level": "progressing"},
            ], "route_phase": None,
            "timetable": None, "recorded": None, "availability_registered": False,
            "pacing": None, "view_hash": "0" * 64,
        }
        _, body = _render(view, date(2026, 10, 2))
        rendered = body.decode("utf-8")
        self.assertIn("&lt;script&gt;&amp;", rendered)
        self.assertNotIn("<script>&", rendered)
        self.assertIn("x&lt;0", rendered)
        self.assertIn("A. &lt;x&amp;", rendered)
        self.assertIn("<details><summary>答案</summary>&lt;script&gt;</details>", rendered)
        self.assertIn("数学一", rendered)
        self.assertIn("对照后：对", rendered)

    def test_today_page_formats_past_question_quotas_cycle_and_zero_minutes(self) -> None:
        view = {
            "date": "2026-10-02", "budget": {"total_minutes": 60,
                "total_source": "config", "base_minutes": 60, "base_source": "config"},
            "preflight": {
                "selected": [{"review_id": "past", "subject_id": "cs408"}],
                "subject_allocation": [{"subject_id": "cs408", "display_name": "计算机学科专业基础"}],
                "subject_review_quotas": {"cs408": 30},
                "subject_review_minutes": {"cs408": 10},
            },
            "reviews": [{"review_id": "past", "title": "真题知识点", "level": "progressing",
                         "question_level": "past_question", "check": "past_question",
                         "question_ref": "cs408-2024-01",
                         "question": {"question_id": "cs408-2024-01", "exam_year": 2024,
                                      "number": "01", "locator": {"page": 8}}}],
            "route_phase": None, "timetable": None,
            "recorded": {"advanced": True, "study_minutes": 0, "reviews": []},
            "availability_registered": False,
            "pacing": {"next_review": "2026-10-05", "unreported_cycles": []},
            "view_hash": "0" * 64,
        }
        _, body = _render(view, date(2026, 10, 2))
        rendered = body.decode("utf-8")
        self.assertIn("真题：cs408-2024-01", rendered)
        self.assertIn("年份 / 题号：2024 / 01", rendered)
        self.assertNotIn("question_id", rendered)
        self.assertNotIn("locator", rendered)
        self.assertIn("计算机学科专业基础 复习配额", rendered)
        self.assertNotIn("cs408 复习配额", rendered)
        self.assertIn("本周期到 2026-10-05 结束，2026-10-06 复盘", rendered)
        self.assertIn("学习分钟：0 分钟", rendered)

    def test_availability_and_record_posts_use_redirect_and_reject_replay(self) -> None:
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        with tempfile.TemporaryDirectory() as temporary:
            workspace = load_workspace(_workspace(Path(temporary), availability=True))
            server = make_server(workspace, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            opener = build_opener(NoRedirect())
            base = f"http://127.0.0.1:{server.server_port}"

            def post(path: str, values: dict[str, str]) -> int:
                request = Request(
                    base + path, data=urlencode(values).encode("utf-8"),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                try:
                    return opener.open(request).status
                except HTTPError as exc:
                    return exc.code

            try:
                today = date.today()
                self.assertEqual(post("/availability", {
                    "date": today.isoformat(), "minutes": "90",
                }), 303)
                from ky.availability import load_availability
                availability_path = workspace.write_target("state.availability")
                self.assertEqual(load_availability(availability_path).days[today], 90)
                unchanged = availability_path.read_bytes()
                self.assertEqual(post("/availability", {
                    "date": today.isoformat(), "minutes": "91", "extra": "x",
                }), 400)
                self.assertEqual(availability_path.read_bytes(), unchanged)
                from ky.today import load_today
                view = load_today(workspace, today)
                values = {"date": today.isoformat(), "view_hash": view["view_hash"],
                          "study_minutes": "20"}
                unknown = {**values, "outcome.unknown": "skip"}
                self.assertEqual(post("/record", unknown), 400)
                self.assertEqual(post("/record", values), 303)
                self.assertEqual(post("/record", values), 400)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
            self.assertFalse(thread.is_alive())

    def test_injected_today_rejects_cross_midnight_record_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = load_workspace(_workspace(Path(temporary)))
            server = make_server(
                workspace, 0, today_provider=lambda: date(2026, 10, 3),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = urlencode({
                    "date": "2026-10-02", "view_hash": "0" * 64,
                    "study_minutes": "10",
                }).encode()
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/record", data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request)
                self.assertEqual(raised.exception.code, 400)
                self.assertFalse(list(workspace.write_target("state.plans").rglob(
                    "completion--*.yaml")))
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_large_post_body_returns_400(self) -> None:
        from ky.web.server import _MAX_BODY

        with tempfile.TemporaryDirectory() as temporary:
            workspace = load_workspace(_workspace(Path(temporary)))
            server = make_server(workspace, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/record",
                    data=b"x" * (_MAX_BODY + 1),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request)
                self.assertEqual(raised.exception.code, 400)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_record_partial_failure_pages_explain_durable_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = load_workspace(_workspace(Path(temporary)))
            server = make_server(
                workspace, 0, today_provider=lambda: date(2026, 10, 2),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            form = urlencode({
                "date": "2026-10-02", "view_hash": "0" * 64, "study_minutes": "10",
            }).encode()
            request = Request(
                base + "/record", data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                for stage, expected in (
                    ("freeze_written", "冻结已触发并记下"),
                    ("event_written", "已记录，复习队列未推进"),
                ):
                    error = RecordPipelineError("injected", stage, record_path="saved")
                    with patch("ky.web.server.record_day", side_effect=error):
                        with self.assertRaises(HTTPError) as raised:
                            urlopen(request)
                    self.assertEqual(raised.exception.code, 400)
                    body = raised.exception.read().decode("utf-8")
                    self.assertIn(expected, body)
                    if stage == "event_written":
                        self.assertIn("/advance", body)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_advance_form_redirects_as_advanced_then_already_advanced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = load_workspace(_workspace(Path(temporary)))
            queue_items = yaml.safe_load(
                (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_text(
                    encoding="utf-8"
                )
            )["items"]
            item = queue_items[0]
            ReviewShardStore(workspace.write_target("state.review_queue")).write([item])
            day = date(2026, 10, 2)
            DayPlanStore(workspace.write_target("state.plans")).write_completion_event(
                CompletionEvent(day, (ReviewCompletion(
                    item["review_id"], day, "recall_vs_notes", "correct",
                ),))
            )
            server = make_server(
                workspace, 0, today_provider=lambda: day,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            opener = build_opener(HTTPRedirectHandler())
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                for expected in ("advanced", "already_advanced"):
                    request = Request(
                        base + "/advance", data=urlencode({"date": day.isoformat()}).encode(),
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    with opener.open(request) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn(expected, response.geturl())
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_web_cli_no_open_prints_address_and_port_conflict_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = _workspace(Path(temporary))

            class FakeServer:
                server_port = 43210

                def serve_forever(self):
                    raise KeyboardInterrupt

                def server_close(self):
                    return None

            output = io.StringIO()
            with patch("ky.web.cli.load_workspace", return_value=object()), \
                    patch("ky.web.cli.make_server", return_value=FakeServer()), \
                    patch("ky.web.cli.webbrowser.open") as open_browser, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(web_main(["--port", "0", "--no-open", "--workspace",
                                           str(registry)]), 0)
            self.assertEqual(output.getvalue(), "http://127.0.0.1:43210/\n")
            open_browser.assert_not_called()

            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sock.listen()
            port = sock.getsockname()[1]
            errors = io.StringIO()
            try:
                with contextlib.redirect_stderr(errors):
                    self.assertEqual(web_main(["--port", str(port), "--no-open",
                                               "--workspace", str(registry)]), 2)
            finally:
                sock.close()
            self.assertIn("端口被占用", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
