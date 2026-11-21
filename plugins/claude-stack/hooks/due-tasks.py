#!/usr/bin/env python3
"""到期任务提醒（Antigravity SessionStart + PreInvocation）：
到了日子，打开任何一个 Antigravity 会话都会自动认领并注入 systemMessage，让主会话立即接手。

约定：
  任务目录 ~/.gemini/due/（测试可用 DUE_TASKS_DIR 覆盖），文件名为 <YYYY-MM-DD>-<名>.md。
  - due/         待办（不存在就当无任务，不建目录、直接返回 {}）
  - due/running/ 已被某会话原子认领（os.rename）
  - due/done/    主会话做完后自行挪入
  - running/<任务名>.ack：主会话收到任务后先创建空文件确认送达。
    无 .ack 超过 30 分钟视为未送达、自动重发；有 .ack 超过 24 小时视为卡住、自动重新认领。

环境变量（测试用）：
  DUE_TASKS_DIR   任务根目录
  DUE_TASKS_TODAY 覆盖「今天」（YYYY-MM-DD）
  DUE_TASKS_NOW   覆盖当前时间戳（秒，浮点数）
"""
import datetime
import json
import os
import re
import sys
import time

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-.+\.md$")
UNACK_STALE_SEC = 30 * 60
ACK_STALE_SEC = 24 * 3600
VALID_EVENTS = ("SessionStart", "PreInvocation")


def parse_due_date(filename):
    m = DATE_RE.match(filename)
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def read_title(path, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s:
                    return s.lstrip("#").strip() or fallback
    except OSError:
        pass
    return fallback


def claim_due_tasks(due_dir, today, now_ts):
    if not os.path.isdir(due_dir):
        return []

    running_dir = os.path.join(due_dir, "running")
    claimed = []

    # 1. Scan due/ for newly due .md files
    try:
        entries = list(os.scandir(due_dir))
    except OSError:
        return []

    due_files = []
    for ent in entries:
        if not ent.is_file(follow_symlinks=False):
            continue
        d = parse_due_date(ent.name)
        if d is not None and d <= today:
            due_files.append((d, ent.name, ent.path))

    if due_files:
        os.makedirs(running_dir, exist_ok=True)
        for _, name, src in sorted(due_files):
            dst = os.path.join(running_dir, name)
            try:
                os.rename(src, dst)
                os.utime(dst, (now_ts, now_ts))
                claimed.append((name, dst, False))
            except OSError:
                continue

    # 2. Scan due/running/ for unacked (>30m) or stuck (>24h) tasks
    if os.path.isdir(running_dir):
        try:
            rentries = list(os.scandir(running_dir))
        except OSError:
            rentries = []
        for ent in sorted(rentries, key=lambda e: e.name):
            if not ent.is_file(follow_symlinks=False):
                continue
            if parse_due_date(ent.name) is None:
                continue
            ack_path = ent.path + ".ack"
            has_ack = os.path.exists(ack_path)
            threshold = ACK_STALE_SEC if has_ack else UNACK_STALE_SEC
            try:
                mtime = ent.stat().st_mtime
            except OSError:
                continue
            if (now_ts - mtime) < threshold:
                continue
            # Atomic reclaim via temporary rename
            tmp = f"{ent.path}.reclaim.{os.getpid()}"
            try:
                os.rename(ent.path, tmp)
            except OSError:
                continue
            try:
                if has_ack:
                    try:
                        os.remove(ack_path)
                    except OSError:
                        pass
                os.utime(tmp, (now_ts, now_ts))
                os.rename(tmp, ent.path)
                claimed.append((ent.name, ent.path, True))
            except OSError:
                try:
                    os.rename(tmp, ent.path)
                except OSError:
                    pass

    return claimed


def format_message(due_dir, claimed):
    done_dir = os.path.join(due_dir, "done")
    lines = [f"[到期任务提醒] 本会话自动认领了 {len(claimed)} 项到期任务："]
    for name, path, reclaimed in claimed:
        title = read_title(path, name)
        tag = "（超时重新认领）" if reclaimed else ""
        lines.append(f"- {title}{tag} -> {path}")
    lines.append(
        f"请先为每项任务创建确认文件 `<任务路径>.ack`（表示已收到），读取任务文件并按正文说明执行；"
        f"完成后把任务文件移到 `{done_dir}/` 并删掉对应的 `.ack` 文件。"
    )
    return "\n".join(lines)


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        print("{}")
        return
    try:
        data = json.loads(raw)
    except Exception:
        print("{}")
        return
    if not isinstance(data, dict):
        print("{}")
        return
    event = data.get("hookEventName")
    if event not in VALID_EVENTS:
        print("{}")
        return

    due_dir = os.environ.get("DUE_TASKS_DIR") or os.path.expanduser("~/.gemini/due")
    today_env = os.environ.get("DUE_TASKS_TODAY")
    try:
        today = datetime.date.fromisoformat(today_env) if today_env else datetime.date.today()
    except ValueError:
        today = datetime.date.today()
    try:
        now_ts = float(os.environ["DUE_TASKS_NOW"]) if "DUE_TASKS_NOW" in os.environ else time.time()
    except ValueError:
        now_ts = time.time()

    try:
        claimed = claim_due_tasks(due_dir, today, now_ts)
    except Exception as e:
        print(json.dumps({
            "injectSteps": [{
                "systemMessage": {"systemMessage": f"[due-tasks] 钩子扫描出错（已放行）：{type(e).__name__}"}
            }]
        }, ensure_ascii=False))
        return

    if not claimed:
        print("{}")
        return

    msg = format_message(due_dir, claimed)
    print(json.dumps({
        "injectSteps": [{
            "systemMessage": {"systemMessage": msg}
        }]
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
