"""fetch_jwc_news 的解析与合并逻辑测试（离线，不发真实请求）"""
import json
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

from urllib3.util import connection as urllib3_connection

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fetchers import fetch_jwc_news as mod  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParseGsHtmlTest(unittest.TestCase):
    """研究生院新版通知公告页（静态 HTML）"""

    def setUp(self):
        self.items = mod.parse_gs_html(load_fixture("gs_tzgg_qb.html"), mod.GS_LIST_URL)

    def test_extracts_title_date_and_absolute_url(self):
        self.assertEqual(len(self.items), 3)
        first = self.items[0]
        self.assertEqual(first["title"], "关于2026年秋季学期研究生课程成绩认定（转录）的通知")
        self.assertEqual(first["date"], "2026-09-12")
        self.assertEqual(first["url"], "https://gsnews.swjtu.edu.cn/info/1637/34844.htm")
        self.assertEqual(first["source"], "研究生院")

    def test_keeps_page_order_and_skips_empty_titles(self):
        self.assertEqual(
            [item["title"] for item in self.items],
            [
                "关于2026年秋季学期研究生课程成绩认定（转录）的通知",
                "关于研究生《体育》课程免修免考的通知",
                "研究生院关于公开招聘研究生助管的通知",
            ],
        )

    def test_ignores_links_that_are_not_articles(self):
        urls = [item["url"] for item in self.items]
        self.assertNotIn("https://gsnews.swjtu.edu.cn/tzggnew/qb.htm", urls)
        self.assertNotIn("https://gsnews.swjtu.edu.cn/index.htm", urls)


class ParseSistResponseTest(unittest.TestCase):
    """信息学院官网（Vue SPA 背后的 JSON 接口）"""

    def setUp(self):
        payload = json.loads(load_fixture("sist_node_rows.json"))
        self.items = mod.parse_sist_response(payload)

    def test_builds_detail_url_from_row_id(self):
        self.assertEqual(len(self.items), 2)
        self.assertEqual(
            self.items[0]["url"],
            "https://sist.swjtu.edu.cn/pc/NrWCF8Dr-wmmIxdXvZPeCQY/"
            "1yaM_T4qiBsFULvLXHbMflQ?id=97nyfCJGZRLXIuHdsLmbuM4e&lang=cn",
        )

    def test_normalizes_publish_time_to_date(self):
        self.assertEqual(self.items[0]["date"], "2026-09-10")
        self.assertEqual(self.items[1]["date"], "2026-09-07")
        self.assertEqual(
            self.items[0]["title"],
            "信息学院2026-2027学年第1学期研究生 “教学实践（创新创业与社会实践）”及“三助”岗位申请通知",
        )
        self.assertEqual(self.items[0]["source"], "信息学院")


class NormalizeDateTest(unittest.TestCase):
    def test_prefer_ipv4_switches_urllib3_family(self):
        """GitHub runner 上出现过 IPv6 无路由，强制 IPv4 是兜底手段"""
        urllib3_connection.allowed_gai_family = lambda: socket.AF_UNSPEC
        self.addCleanup(
            setattr, urllib3_connection, "allowed_gai_family", lambda: socket.AF_UNSPEC
        )

        mod.prefer_ipv4()

        self.assertEqual(urllib3_connection.allowed_gai_family(), socket.AF_INET)

    def test_accepts_dot_slash_and_dash_separators(self):
        self.assertEqual(mod.normalize_date("2026.09.12"), "2026-09-12")
        self.assertEqual(mod.normalize_date("2026-09-10 17:00:23"), "2026-09-10")
        self.assertEqual(mod.normalize_date("2026/9/5"), "2026-09-05")

    def test_returns_empty_string_when_no_date(self):
        self.assertEqual(mod.normalize_date(""), "")
        self.assertEqual(mod.normalize_date("待定"), "")


class MergeItemsTest(unittest.TestCase):
    def test_dedupes_by_title_and_sorts_by_date_desc(self):
        gs = [
            {"title": "通知A", "date": "2026-09-10", "url": "https://gs/a"},
            {"title": "通知B", "date": "2026-09-12", "url": "https://gs/b"},
        ]
        sist = [
            {"title": "通知A", "date": "2026-09-11", "url": "https://sist/a"},
            {"title": "通知C", "date": "2026-09-01", "url": "https://sist/c"},
        ]

        merged = mod.merge_items([gs, sist])

        self.assertEqual([item["title"] for item in merged], ["通知B", "通知A", "通知C"])
        self.assertEqual(merged[1]["url"], "https://gs/a")

    def test_items_without_date_go_last(self):
        merged = mod.merge_items([
            [{"title": "无日期", "date": "", "url": "https://gs/x"}],
            [{"title": "有日期", "date": "2026-09-01", "url": "https://sist/y"}],
        ])
        self.assertEqual([item["title"] for item in merged], ["有日期", "无日期"])


class FetchJwcNewsTest(unittest.TestCase):
    def setUp(self):
        # fetch_jwc_news 会把每个源的抓取情况打印出来，测试里没必要污染输出
        patcher = mock.patch("builtins.print")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_keeps_working_source_when_the_other_fails(self):
        with mock.patch.object(
            mod, "fetch_gs_news", side_effect=RuntimeError("研究生院挂了")
        ), mock.patch.object(
            mod, "fetch_sist_news", return_value=[{"title": "学院通知", "date": "2026-09-10", "url": "u"}]
        ):
            items = mod.fetch_jwc_news()

        self.assertEqual([item["title"] for item in items], ["学院通知"])

    def test_raises_when_every_source_fails(self):
        with mock.patch.object(
            mod, "fetch_gs_news", side_effect=RuntimeError("研究生院挂了")
        ), mock.patch.object(
            mod, "fetch_sist_news", side_effect=RuntimeError("学院挂了")
        ):
            with self.assertRaises(RuntimeError):
                mod.fetch_jwc_news()


if __name__ == "__main__":
    unittest.main()
