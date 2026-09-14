"""校验邮件里的通知卡片带来源标签（离线，纯渲染）"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import send_email  # noqa: E402


class NoticeSourceBadgeTest(unittest.TestCase):
    def test_four_part_line_renders_source_badge(self):
        html = send_email.render_jwc_cards(
            "【需要行动】\n信息学院|||某学院通知|||https://sist.swjtu.edu.cn/a|||今天17点截止"
        )
        self.assertIn("信息学院</span>", html)
        self.assertIn("某学院通知", html)
        self.assertIn("https://sist.swjtu.edu.cn/a", html)

    def test_three_part_line_still_renders_without_badge(self):
        """兼容老的 daily_brief.md（AI 万一没按新格式输出也不能崩）"""
        html = send_email.render_jwc_cards(
            "【需要行动】\n旧格式通知|||https://gsnews.swjtu.edu.cn/a|||说明"
        )
        self.assertIn("旧格式通知", html)
        self.assertIn("https://gsnews.swjtu.edu.cn/a", html)
        self.assertNotIn("<span", html)


class CollectSeenItemsTest(unittest.TestCase):
    def test_reads_title_and_url_from_four_part_lines(self):
        seen = send_email.collect_seen_items(
            {"jwc": "信息学院|||某学院通知|||https://sist.swjtu.edu.cn/a|||说明\n"}
        )
        self.assertEqual(seen, [{"title": "某学院通知", "url": "https://sist.swjtu.edu.cn/a"}])

    def test_reads_title_and_url_from_three_part_lines(self):
        seen = send_email.collect_seen_items(
            {"jwc": "旧格式通知|||https://gsnews.swjtu.edu.cn/a|||说明\n"}
        )
        self.assertEqual(seen, [{"title": "旧格式通知", "url": "https://gsnews.swjtu.edu.cn/a"}])


if __name__ == "__main__":
    unittest.main()
