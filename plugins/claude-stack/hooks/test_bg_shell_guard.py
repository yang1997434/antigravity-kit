"""后台 shell 闸测试：python3 -m unittest test_bg_shell_guard.py"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "bg-shell-guard.py")


def run_hook(cmd, extra_args=None, in_rex=True, tool="run_command"):
    env = dict(os.environ)
    if in_rex:
        env["REX_SESSION"] = "session:test"
    else:
        env.pop("REX_SESSION", None)
    args = {"CommandLine": cmd, "WaitMsBeforeAsync": 5000}
    if extra_args:
        args.update(extra_args)
    payload = {"hookEventName": "PreToolUse", "toolCall": {"id": "t1", "name": tool, "args": args}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


class BgShellGuardTests(unittest.TestCase):
    def test_denies_costly_background_command_inside_rex(self):
        out = run_hook("./deploy/deploy.sh prod", extra_args={"WaitMsBeforeAsync": 500})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("jobs", out["reason"])

        out2 = run_hook("ffmpeg -i in.mp4 out.mp4", extra_args={"IsDaemon": True})
        self.assertEqual(out2["decision"], "deny")

        out3 = run_hook("rsync -av /a /b &")
        self.assertEqual(out3["decision"], "deny")

    def test_allows_outside_rex_or_foreground_or_non_costly(self):
        self.assertEqual(run_hook("./deploy/deploy.sh prod", extra_args={"WaitMsBeforeAsync": 500}, in_rex=False)["decision"], "allow")
        self.assertEqual(run_hook("./deploy/deploy.sh prod", extra_args={"WaitMsBeforeAsync": 10000})["decision"], "allow")
        self.assertEqual(run_hook("npm run dev", extra_args={"IsDaemon": True})["decision"], "allow")

    def test_allows_rex_job_and_denies_wrong_rex_session(self):
        self.assertEqual(run_hook("rex-job run deploy /tmp/d.log './deploy.sh'", extra_args={"WaitMsBeforeAsync": 500})["decision"], "allow")
        self.assertEqual(run_hook("rex run -s jobs -- ./deploy.sh", extra_args={"WaitMsBeforeAsync": 500})["decision"], "allow")
        out = run_hook("rex run -s work -- rex-job run deploy /tmp/d.log './deploy.sh'")
        self.assertEqual(out["decision"], "deny")


if __name__ == "__main__":
    unittest.main()
