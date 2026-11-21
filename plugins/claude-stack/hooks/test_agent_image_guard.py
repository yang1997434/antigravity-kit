"""图片核对分流闸测试：python3 -m unittest test_agent_image_guard.py"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "agent-image-guard.py")


def run_hook(tool_name, args):
    payload = {"hookEventName": "PreToolUse", "toolCall": {"id": "t1", "name": tool_name, "args": args}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


class AgentImageGuardTests(unittest.TestCase):
    def test_denies_heavy_subagent_for_image_inspection(self):
        out = run_hook("invoke_subagent", {"TypeName": "worker", "Role": "UI Check", "Prompt": "请逐张检查 /tmp/home-375.png 和 /tmp/home-1280.png"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("checker", out["reason"])

    def test_allows_checker_flash_image_generator_and_bypass(self):
        self.assertEqual(run_hook("invoke_subagent", {"TypeName": "checker", "Role": "UI Check", "Prompt": "看 /tmp/a.png"})["decision"], "allow")
        self.assertEqual(run_hook("invoke_subagent", {"TypeName": "image-generator", "Role": "Gen", "Prompt": "生成 hero.png"})["decision"], "allow")
        self.assertEqual(run_hook("invoke_subagent", {"TypeName": "worker", "Model": "flash", "Prompt": "看 /tmp/a.png"})["decision"], "allow")
        self.assertEqual(run_hook("invoke_subagent", {"TypeName": "coder", "Prompt": "非看图任务\n写脚本生成 demo.png"})["decision"], "allow")
        # Plain mention of 截图 without image filename / 联络表 / 抽帧 / 逐张 is allowed
        self.assertEqual(run_hook("invoke_subagent", {"TypeName": "coder", "Prompt": "改完前端后自跑 playwright 截图脚本"})["decision"], "allow")

    def test_swarm_and_workflow_guards(self):
        out = run_hook("swarm", {"action": "add", "name": "worker-1", "model": "gemini-4-neon-high", "brief": "核对联络表里的 10 张图"})
        self.assertEqual(out["decision"], "deny")

        self.assertEqual(run_hook("swarm", {"action": "add", "name": "checker-1", "model": "gemini-3.8-flash-medium", "brief": "核对联络表"})["decision"], "allow")
        self.assertEqual(run_hook("swarm", {"action": "status"})["decision"], "allow")

        wf_bad = run_hook("run_workflow", {"Script": "agent('检查 /tmp/frame_01.jpg 是否错位')"})
        self.assertEqual(wf_bad["decision"], "deny")

        wf_ok = run_hook("run_workflow", {"Script": "agent('检查 /tmp/frame_01.jpg', type_name='checker')"})
        self.assertEqual(wf_ok["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
