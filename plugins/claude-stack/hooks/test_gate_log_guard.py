"""门禁输出闸的测试：python3 -m unittest test_gate_log_guard.py"""
import importlib.util, json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "gate-log-guard.py")
spec = importlib.util.spec_from_file_location("gate_log_guard", HOOK)
assert spec and spec.loader
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def run_claude(cmd, mode="pre", tool="Bash", home=None):
    env = dict(os.environ, HOME=home or os.environ["HOME"])
    p = subprocess.run([sys.executable, HOOK, mode], input=json.dumps({"tool_name": tool, "tool_input": {"command": cmd}, "cwd": "/x"}),
                       capture_output=True, text=True, env=env)
    return json.loads(p.stdout)["hookSpecificOutput"] if p.stdout.strip() else None


def run_agy(cmd, mode="pre", tool="run_command", home=None):
    env = dict(os.environ, HOME=home or os.environ["HOME"])
    payload = {"hookEventName": "PreToolUse", "cwd": "/x", "toolCall": {"id": "t1", "name": tool, "args": {"CommandLine": cmd}}}
    p = subprocess.run([sys.executable, HOOK, mode], input=json.dumps(payload), capture_output=True, text=True, env=env)
    return json.loads(p.stdout)


class Rewrite(unittest.TestCase):
    def test_pytest_tail_rewritten(self):
        new = g.rewrite("export TMPDIR=$(mktemp -d -p ~/.cache) && uv run python -m pytest tests/test_a.py -q 2>&1 | tail -5", "/l/x.log")
        self.assertEqual(new, "export TMPDIR=$(mktemp -d -p ~/.cache) && ( set -o pipefail; uv run python -m pytest tests/test_a.py -q 2>&1 | tee /l/x.log | tail -5 )")

    def test_adds_stderr_merge_when_missing(self):
        self.assertEqual(g.rewrite("npm test | tail -20; echo done", "/l/x.log"), "( set -o pipefail; npm test 2>&1 | tee /l/x.log | tail -20 ); echo done")

    def test_rewritten_command_keeps_test_exit_code(self):
        new = g.rewrite("sh -c 'echo boom; exit 3' | tail -1", "/dev/null")
        self.assertIsNone(new)
        new = g.rewrite("pytest() { echo boom; return 3; }; pytest | tail -1", "/dev/null")
        self.assertIsNotNone(new)
        p = subprocess.run(["bash", "-c", new], capture_output=True, text=True)
        self.assertEqual(p.returncode, 3)
        self.assertIn("boom", p.stdout)

    def test_file_names_are_not_runners(self):
        for cmd in ("ls pytest.ini setup.cfg | head -3", "ls jest.config.js | head", "cat my-pytest-notes | tail -2"):
            self.assertFalse(g.hit(cmd), cmd)
        self.assertTrue(g.hit("uv run pytest -q | tail -3"))
        self.assertTrue(g.hit("python3 -m unittest test_x.py | tail -3"))

    def test_unwritable_log_dir_tells_model(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".cache"))
            with open(os.path.join(home, ".cache", "claude-gate-log"), "w", encoding="utf-8"):
                pass
            out = run_claude("uv run pytest -q | tail -3", home=home)
            self.assertIn("建不了日志目录", out["additionalContext"])
            self.assertNotIn("updatedInput", out)

    def test_heredoc_not_rewritten(self):
        cmd = "python3 - <<'EOF'\nprint('pytest | tail')\nEOF\npytest -q | tail -3"
        self.assertIsNone(g.rewrite(cmd, "/l/x.log"))
        self.assertTrue(g.hit(cmd))

    def test_tee_log_or_pipefail_not_hit(self):
        self.assertFalse(g.hit("pytest -q 2>&1 | tee gate.log | tail -5; exit ${PIPESTATUS[0]}"))
        self.assertFalse(g.hit("( set -o pipefail; pytest -q 2>&1 | tail -5 )"))
        self.assertFalse(g.hit("pnpm test > gate.log 2>&1; echo exit=$?; tail -5 gate.log"))

    def test_quoted_runner_word_in_grep_ignored(self):
        self.assertFalse(g.hit("grep -n 'DATABASE_URL\\|pytest' .github/workflows/*.yml | head -20"))

    def test_runner_then_other_pipe_then_tail_ignored(self):
        self.assertFalse(g.hit("pytest -q 2>&1 | grep -E 'FAIL|passed' | head -3"))
        self.assertFalse(g.hit("git log --oneline | tail -5"))


class Hook(unittest.TestCase):
    def test_pre_mode_returns_updated_input_and_logs_hit(self):
        with tempfile.TemporaryDirectory() as home:
            out = run_claude("pytest -q 2>&1 | tail -3", home=home)
            self.assertEqual(out["permissionDecision"], "allow")
            self.assertIn("set -o pipefail; pytest -q 2>&1 | tee ", out["updatedInput"]["command"])
            with open(os.path.join(home, ".cache/claude-gate-log/hits.jsonl"), encoding="utf-8") as f:
                hits = f.read().splitlines()
            self.assertTrue(json.loads(hits[0])["rewritten"])

    def test_antigravity_simple_test_rewrites_and_allows(self):
        with tempfile.TemporaryDirectory() as home:
            out = run_agy("pytest -q | tail -5", home=home)
            self.assertEqual(out["decision"], "allow")
            self.assertIn("set -o pipefail; pytest -q 2>&1 | tee ", out["overwrite"]["CommandLine"])

    def test_antigravity_compound_command_rewrites_properly(self):
        with tempfile.TemporaryDirectory() as home:
            out = run_agy("cd /tmp && pytest -q | tail -5", home=home)
            self.assertEqual(out["decision"], "allow")
            self.assertIn("set -o pipefail; pytest -q 2>&1 | tee ", out["overwrite"]["CommandLine"])

    def test_antigravity_non_matching_or_heredoc_returns_allow_without_overwrite(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(run_agy("git status"), {"decision": "allow"})
            self.assertEqual(run_agy("pytest | tail", tool="read_file"), {"decision": "allow"})
            self.assertEqual(run_agy("cat <<'EOF'\n1\nEOF\npytest | tail -3", home=home), {"decision": "allow"})

    def test_other_tool_ignored(self):
        self.assertIsNone(run_claude("pytest | tail", tool="Read"))


if __name__ == "__main__":
    unittest.main()
