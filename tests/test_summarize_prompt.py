"""校验摘要提示词真的用上了环境变量里的用户画像与方向（离线，不调 AI）"""
import importlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

PROFILE = "身份：某大学信息学院研究生，方向是通信与信息系统"
DIRECTION = "机器人算法"


class SummarizePromptTest(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ["USER_NAME"] = "测试用户"
        os.environ["USER_PROFILE_TEXT"] = PROFILE
        os.environ["USER_DIRECTION"] = DIRECTION

        import summarize
        self.mod = importlib.reload(summarize)
        self.mod.call_deepseek = lambda prompt: prompt  # 直接把提示词当返回值，方便断言

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        importlib.reload(self.mod)

    def test_action_advice_prompt_uses_profile_from_env(self):
        prompt = self.mod.generate_action_advice("待办", "科技", "榜单", "经济", "政治", "科学")
        self.assertIn(PROFILE, prompt)

    def test_overview_prompt_uses_configured_direction(self):
        prompt = self.mod.summarize_overview("通知摘要", "科技摘要")
        self.assertIn(DIRECTION, prompt)
        self.assertNotIn("AI PM", prompt)


if __name__ == "__main__":
    unittest.main()
