#!/usr/bin/env python3
"""图片核对分流闸（Antigravity PreToolUse(invoke_subagent|run_workflow|swarm)）：
拦截把看图/核对截图/抽帧任务派给重型代理（如 self / worker / coder / researcher / reviewer），
强制改派轻量 `checker`（flash 模型，一次 ≤ 20 张）。
如果任务并不是看图核对（如起服务截图、写渲染脚本、生成图片），在提示词里写一行「非看图任务」即放行。
出错或输入异常一律放行。
"""
import json
import re
import sys

IMG_RE = re.compile(r"\.(?:png|jpe?g|webp|gif)\b|联络表|抽帧|逐张", re.I)
BYPASS_MARK = "非看图任务"
ALLOWED_SUBAGENTS = {"checker", "image-generator"}
FLASH_MODEL_RE = re.compile(r"flash", re.I)

WHY = (
    "图片核对请改派 `checker`（单路用 `Model: \"flash\"`，Swarm 用 `gemini-3.8-flash-medium`，一次 ≤ 20 张；"
    "超过 20 张先拼联络表或拆分多个 checker），避免高价重型模型烧额度。"
    "若这不是看图核对任务（如写截图脚本、生成素材），请在任务描述中加一行「非看图任务」再派。"
)


def check(payload):
    tc = payload.get("toolCall") or {}
    name = tc.get("name")
    args = tc.get("args") or {}
    if not isinstance(args, dict):
        return {"decision": "allow"}

    if name == "invoke_subagent":
        tname = str(args.get("TypeName") or "").lower()
        model = str(args.get("Model") or "").lower()
        if tname in ALLOWED_SUBAGENTS or FLASH_MODEL_RE.search(model):
            return {"decision": "allow"}
        text = f"{args.get('Role') or ''}\n{args.get('Prompt') or ''}"
        if BYPASS_MARK not in text and IMG_RE.search(text):
            return {"decision": "deny", "reason": WHY}
        return {"decision": "allow"}

    if name == "swarm":
        if args.get("action") != "add":
            return {"decision": "allow"}
        wname = str(args.get("name") or "").lower()
        model = str(args.get("model") or "").lower()
        if "checker" in wname or FLASH_MODEL_RE.search(model):
            return {"decision": "allow"}
        text = str(args.get("brief") or "")
        if BYPASS_MARK not in text and IMG_RE.search(text):
            return {"decision": "deny", "reason": WHY}
        return {"decision": "allow"}

    if name == "run_workflow":
        script = str(args.get("Script") or "")
        if not script and isinstance(args.get("ScriptPath"), str):
            try:
                with open(args["ScriptPath"], encoding="utf-8") as f:
                    script = f.read()
            except OSError:
                return {"decision": "allow"}
        if not script or BYPASS_MARK in script or not IMG_RE.search(script):
            return {"decision": "allow"}
        # Allow if workflow explicitly routes agent calls to checker or flash
        if re.search(r"['\"]checker['\"]|flash", script, re.I):
            return {"decision": "allow"}
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
