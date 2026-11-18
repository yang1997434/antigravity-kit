#!/usr/bin/env python3
"""门禁输出闸：测试命令直接接 `| tail` / `| head` 的命令，自动改写成
`( set -o pipefail; <测试命令> 2>&1 | tee <日志> | tail … )`，尾巴照看、退出码变成测试本身的、完整输出留在日志里。
同时兼容 Antigravity PreToolUse(run_command -> overwrite.CommandLine) 与 Claude Code PreToolUse(Bash -> updatedInput.command)。
带 heredoc 的命令不改写（怕改到脚本正文）。"""
import json, os, re, sys, time

RUNNER = r"(?:pytest|vitest|jest|npm (?:run )?test|pnpm (?:run )?test|cargo test|go test|playwright test|-m unittest)"
RUNNER_RE = re.compile(r"(?<![\w.-])" + RUNNER + r"(?![\w.])")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
SEP = re.compile(r"\n|;|&&|\|\|")
TAIL = re.compile(r"\s*(?:tail|head)\b")
LOGGED = re.compile(r"\btee\b|\.log\b|PIPESTATUS|pipefail")
LOG_DIR = os.path.expanduser("~/.cache/claude-gate-log")
HINT = ("门禁输出不要直接接 | tail / | head，改成写日志再看尾巴、退出码取测试本身的："
        "`( set -o pipefail; <测试命令> 2>&1 | tee $TMPDIR/gate.log | tail -5 )`。")


def masked(cmd):
    """引号内容换成等长空格，位置不变：grep 'pytest' 这类引号里的词不算测试命令。"""
    return QUOTED.sub(lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], cmd)


def find(cmd):
    """返回 (段起点, 管道竖线位置, 段终点)：测试命令所在的管道段紧接着 | tail / | head。整条命令已写日志则不算。"""
    if LOGGED.search(cmd):
        return None
    m = masked(cmd)
    start = 0
    for sep in list(SEP.finditer(m)) + [None]:
        end = sep.start() if sep else len(m)
        seg = m[start:end]
        pipes = [i for i, ch in enumerate(seg) if ch == "|"]
        for a, b in zip([-1] + pipes, pipes):
            if RUNNER_RE.search(seg[a + 1:b]) and TAIL.match(seg[b + 1:]):
                return start, start + b, end
        start = sep.end() if sep else end
    return None


def hit(cmd):
    return find(cmd) is not None


def rewrite(cmd, log):
    """把命中的管道段改成 ( set -o pipefail; <左> 2>&1 | tee <log> | <右> )。带 heredoc 的不改。"""
    pos = find(cmd)
    if pos is None or "<<" in cmd:
        return None
    s, p, e = pos
    lead = len(cmd[s:p]) - len(cmd[s:p].lstrip())
    s += lead
    left, right = cmd[s:p].rstrip(), cmd[p + 1:e].strip()
    if not re.search(r"2>&1\s*$", left):
        left += " 2>&1"
    return cmd[:s] + f"( set -o pipefail; {left} | tee {log} | {right} )" + cmd[e:]


def handle_antigravity(d, mode):
    tc = d.get("toolCall") or {}
    if tc.get("name") != "run_command" or mode != "pre":
        print('{"decision":"allow"}')
        return
    args = tc.get("args") or {}
    cmd = args.get("CommandLine", "")
    if not hit(cmd):
        print('{"decision":"allow"}')
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        print('{"decision":"allow"}')
        return
    log = os.path.join(LOG_DIR, time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}.log")
    new = rewrite(cmd, log)
    try:
        with open(os.path.join(LOG_DIR, "hits.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "cwd": d.get("cwd"),
                                "rewritten": bool(new), "cmd": cmd[:300]}, ensure_ascii=False) + "\n")
    except OSError:
        pass
    if not new:
        print('{"decision":"allow"}')
        return
    decision = "allow"
    print(json.dumps({
        "decision": decision,
        "reason": f"门禁闸已把测试命令改写成 pipefail + tee，完整输出在 {log}，退出码是测试本身的。",
        "overwrite": {"CommandLine": new}
    }, ensure_ascii=False))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    raw = sys.stdin.read()
    if not raw.strip():
        print("{}")
        return
    d = json.loads(raw)
    if "toolCall" in d or "hookEventName" in d:
        handle_antigravity(d, mode)
        return
    if d.get("tool_name") != "Bash":
        return
    cmd = (d.get("tool_input") or {}).get("command", "")
    if not hit(cmd):
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError as e:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse" if mode == "pre" else "PostToolUse",
                                                 "additionalContext": f"门禁闸建不了日志目录 {LOG_DIR}（{e}），这次没改写；" + HINT}},
                         ensure_ascii=False))
        return
    log = os.path.join(LOG_DIR, time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}.log")
    new = rewrite(cmd, log) if mode == "pre" else None
    try:
        with open(os.path.join(LOG_DIR, "hits.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "cwd": d.get("cwd"), "rewritten": bool(new),
                                "cmd": cmd[:300]}, ensure_ascii=False) + "\n")
    except OSError:
        pass
    if new:
        out = {"hookEventName": "PreToolUse", "permissionDecision": "allow",
               "updatedInput": dict(d.get("tool_input") or {}, command=new),
               "additionalContext": f"门禁闸已把测试命令改写成 pipefail + tee，完整输出在 {log}，退出码是测试本身的。"}
    else:
        out = {"hookEventName": "PreToolUse" if mode == "pre" else "PostToolUse", "additionalContext": HINT}
    print(json.dumps({"hookSpecificOutput": out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
