"""校验邮件里各版块的上下顺序（离线，纯字符串渲染）"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import send_email  # noqa: E402

SECTIONS = {
    "greeting": "【开头】\n早安问候内容\n【结尾】\n晚安内容",
    "jwc": "【需要行动】\n选课通知|||https://gsnews.swjtu.edu.cn/info/1637/34794.htm|||今天去选课",
    "overview": "【今日一句话】\n总览一句话\n【AI观察】\n观察内容\n【趋势预测】\n预测内容",
    "top_picks": "GitHub|||某项目|||https://github.com/a/b|||标签|||摘要|||点评",
    "tech": "某媒体|||某条科技新闻|||https://example.com/a|||标签|||摘要|||点评",
    "action": "【可能的方向】\n方向A|||理由是A\n【今日推荐行动】\n今天先做A",
}


class EmailSectionOrderTest(unittest.TestCase):
    def setUp(self):
        self.html = send_email.build_html("2026-09-14", "morning", SECTIONS)

    def test_greeting_stays_at_the_very_top(self):
        self.assertLess(
            self.html.index("早安问候内容"),
            self.html.index("选课通知"),
        )

    def test_notice_cards_come_before_overview(self):
        self.assertLess(
            self.html.index("选课通知"),
            self.html.index("总览一句话"),
        )

    def test_technology_sections_keep_their_order(self):
        order = ["总览一句话", "🏆 各榜单头名", "科技资讯全览", "🎯 今日行动建议", "今日最该做的一件事"]
        positions = [self.html.index(marker) for marker in order]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
