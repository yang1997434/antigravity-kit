#!/usr/bin/env python3
"""后台 shell 闸（Antigravity PreToolUse(run_command)）：
仅在 Rex 会话内（存在 REX_SESSION）生效：
1. 拦截把中断有代价的命令（部署、迁移、同步、渲染、采集）放到普通后台任务跑（会随客户端关闭中断），
   提示改放 Rex 的 jobs 会话（rex-job run 或 rex run -s jobs）。
2. 拦截把 `rex run ... -- rex-job ...` 开到非 jobs 会话的误操作。
不在 Rex 里、或是短前台命令、或已套 rex-job / -s jobs 的直接放行。出错一律放行。
"""
import json
import os
import re
import sys

WHY = (
    "部署、迁移、同步、渲染、采集这类中断有代价的任务不要直接放普通后台（客户端关闭会被中断），"
    "请改放到 Rex 的 jobs 会话：`rex-job run <名> <日志> '<命令>'` 或 `rex run -s jobs -- <命令>`。"
)

WHY_WRONG_SESSION = (
    "`rex run ... -- rex-job` 必须开在 `jobs` 会话（带 `-s jobs`），否则跑完不会自动清理标签页。"
)

COSTLY_RE = re.compile(
    r"\bdeploy(?:\.sh|\b)|\bmigrat|\balembic\b|\bprisma\s+(?:migrate|db\s+push)|\bscp\b|\brsync\b|\brclone\b|"
    r"\bffmpeg\b|\bremotion\b|\bscrapy\b|\bcrawl|\bgsutil\b",
    re.I,
)

ALREADY_IN_REX_JOBS_RE = re.compile(
    r"\brex-job\s+run\b|\brex\b[^\n]*?(?:-s|--session)(?:=|\s+)[\"']?jobs\b"
)

SHELL_BG_RE = re.compile(r"(?:^|[;&\n])\s*nohup\b|(?:^|[^>&])&\s*(?:$|#)")


def is_wrong_rex_session(cmd):
    if not re.search(r"\brex\s+run\b[^|;&\n]*\s--\s+(?:env\s+(?:\S+=\S+\s+)*)?rex-job\b", cmd):
        return False
    return "rex-job jobs" not in cmd and not re.search(r"(?:-s|--session)(?:=|\s+)[\"']?jobs\b", cmd)


def is_background_intent(args, cmd):
    if args.get("IsDaemon") is True:
        return True
    wait_ms = args.get("WaitMsBeforeAsync")
    if isinstance(wait_ms, (int, float)) and wait_ms <= 1000:
        return True
    if SHELL_BG_RE.search(cmd):
        return True
    return False


def check(payload, env=None):
    env = env if env is not None else os.environ
    tc = payload.get("toolCall") or {}
    if tc.get("name") != "run_command":
        return {"decision": "allow"}
    args = tc.get("args") or {}
    cmd = args.get("CommandLine") or ""
    if not isinstance(cmd, str) or not cmd.strip():
        return {"decision": "allow"}

    if is_wrong_rex_session(cmd):
        return {"decision": "deny", "reason": WHY_WRONG_SESSION}

    if not env.get("REX_SESSION"):
        return {"decision": "allow"}

    if ALREADY_IN_REX_JOBS_RE.search(cmd):
        return {"decision": "allow"}

    if is_background_intent(args, cmd) and COSTLY_RE.search(cmd):
        return {"decision": "deny", "reason": WHY}

    return {"decision": "allow"}


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        print('{"decision":"allow"}')
        return
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            print('{"decision":"allow"}')
            return
        res = check(payload)
    except Exception:
        res = {"decision": "allow"}
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
