"""到期任务提醒钩子测试：python3 -m unittest test_due_tasks.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "due-tasks.py")


def run_hook(event, due_dir, today="2026-11-21", now_ts=1795200000.0):
    env = dict(os.environ, DUE_TASKS_DIR=due_dir, DUE_TASKS_TODAY=today, DUE_TASKS_NOW=str(now_ts))
    payload = {"hookEventName": event, "cwd": "/tmp", "conversationId": "conv-1"}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


class DueTasksTests(unittest.TestCase):
    def test_missing_due_dir_returns_empty_and_does_not_create(self):
        with tempfile.TemporaryDirectory() as td:
            due = os.path.join(td, "due")
            out = run_hook("SessionStart", due)
            self.assertEqual(out, {})
            self.assertFalse(os.path.exists(due))

    def test_claims_due_task_and_ignores_future_and_invalid_names(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "2026-11-20-check-backup.md"), "w", encoding="utf-8") as f:
                f.write("# 检查备份日志\n确认昨天备份成功。\n")
            with open(os.path.join(td, "2026-11-25-future.md"), "w", encoding="utf-8") as f:
                f.write("# 未来任务\n")
            with open(os.path.join(td, "2026-02-30-bad-date.md"), "w", encoding="utf-8") as f:
                f.write("# 非法日期\n")
            with open(os.path.join(td, "notes.md"), "w", encoding="utf-8") as f:
                f.write("# 普通笔记\n")

            out = run_hook("SessionStart", td)
            steps = out.get("injectSteps", [])
            self.assertEqual(len(steps), 1)
            msg = steps[0]["systemMessage"]["systemMessage"]
            self.assertIn("检查备份日志", msg)
            self.assertNotIn("未来任务", msg)
            self.assertTrue(os.path.exists(os.path.join(td, "running", "2026-11-20-check-backup.md")))
            self.assertFalse(os.path.exists(os.path.join(td, "2026-11-20-check-backup.md")))

            # Second run immediately does not duplicate
            out2 = run_hook("PreInvocation", td, now_ts=1795200060.0)
            self.assertEqual(out2, {})

    def test_reclaims_unacked_after_30m_and_acked_after_24h(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "2026-11-21-retry.md"), "w", encoding="utf-8") as f:
                f.write("# 超时重发测试\n")
            t0 = 1795200000.0
            run_hook("SessionStart", td, now_ts=t0)

            # Still fresh after 10 min
            self.assertEqual(run_hook("PreInvocation", td, now_ts=t0 + 600), {})

            # Reclaimed after 31 min without .ack
            out_unack = run_hook("PreInvocation", td, now_ts=t0 + 1860)
            self.assertIn("超时重新认领", out_unack["injectSteps"][0]["systemMessage"]["systemMessage"])

            # Create .ack -> not reclaimed after 2 hours
            running_file = os.path.join(td, "running", "2026-11-21-retry.md")
            ack_file = running_file + ".ack"
            with open(ack_file, "w", encoding="utf-8"):
                pass
            self.assertEqual(run_hook("PreInvocation", td, now_ts=t0 + 1860 + 7200), {})

            # Reclaimed after >24h even with .ack, and .ack is cleared
            out_stuck = run_hook("PreInvocation", td, now_ts=t0 + 1860 + 90000)
            self.assertIn("超时重新认领", out_stuck["injectSteps"][0]["systemMessage"]["systemMessage"])
            self.assertFalse(os.path.exists(ack_file))

    def test_unrelated_event_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "2026-11-21-x.md"), "w", encoding="utf-8") as f:
                f.write("# x\n")
            self.assertEqual(run_hook("PreToolUse", td), {})
            self.assertTrue(os.path.exists(os.path.join(td, "2026-11-21-x.md")))


if __name__ == "__main__":
    unittest.main()
