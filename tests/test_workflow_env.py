"""校验定时任务把脚本需要的变量都透传下去了（离线，只读文件）"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily-brief.yml"


class WorkflowEnvTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_forwards_user_name_secret(self):
        self.assertIn("USER_NAME: ${{ secrets.USER_NAME }}", self.text)

    def test_forwards_user_profile_secret(self):
        self.assertIn("USER_PROFILE_TEXT: ${{ secrets.USER_PROFILE_TEXT }}", self.text)


if __name__ == "__main__":
    unittest.main()
