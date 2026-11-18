#!/usr/bin/env python3
"""Parallel.ai 检索/抓正文的命令行封装。

  search  <query> [-n N] [--after YYYY-MM-DD] [--include d1,d2] [--exclude d1,d2] [--json]
  extract <url> [url ...] [--json]

Key 用 flow-cred 取 PARALLEL_API_KEY，永不打印。
（注意：~/.pi/web-search.json 里的 parallelApiKey 是 `!command` 引用形式，不能直接用。）
"""
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

SEARCH_URL = "https://api.parallel.ai/v1/search"
EXTRACT_URL = "https://api.parallel.ai/v1/extract"


def api_key() -> str:
    import os, shutil
    key = os.environ.get("PARALLEL_API_KEY", "").strip()
    if not key and shutil.which("flow-cred"):
        key = subprocess.run(["flow-cred", "PARALLEL_API_KEY"], capture_output=True, text=True).stdout.strip()
    if not key:
        sys.exit("未找到 PARALLEL_API_KEY（请设置环境变量 PARALLEL_API_KEY）")
    return key


def post(url: str, body: dict) -> dict:
    key = api_key()
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"x-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300].replace(key, "<redacted>")
        sys.exit(f"Parallel API error {e.code}: {detail}")
    except Exception as e:  # 网络层失败
        sys.exit(f"Parallel API request failed: {type(e).__name__}: {str(e).replace(key, '<redacted>')}")


def cmd_search(a) -> None:
    policy = {}
    if a.include:
        policy["include_domains"] = [d.strip() for d in a.include.split(",") if d.strip()]
    if a.exclude:
        policy["exclude_domains"] = [d.strip() for d in a.exclude.split(",") if d.strip()]
    if a.after:
        policy["after_date"] = a.after
    advanced = {"max_results": max(1, min(a.n, 20))}
    if policy:
        advanced["source_policy"] = policy
    queries = a.query if len(a.query) > 1 else [a.query[0]]
    data = post(SEARCH_URL, {
        "objective": a.objective or a.query[0],
        "search_queries": queries,
        "advanced_settings": advanced,
    })
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    results = data.get("results") or []
    if not results:
        print("(no results)")
        return
    for i, it in enumerate(results, 1):
        print(f"[{i}] {it.get('title') or 'Untitled'}")
        print(f"    {it.get('url')}")
        for ex in (it.get("excerpts") or [])[:2]:
            print(f"    {' '.join(str(ex).split())[:400]}")
        print()


def cmd_extract(a) -> None:
    body = {"urls": a.urls, "advanced_settings": {"full_content": True}}
    if a.objective:
        body["objective"] = a.objective
    data = post(EXTRACT_URL, body)
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    results = data.get("results") or []
    if not results:
        print("(no content extracted)", data.get("errors") or "")
        return
    for it in results:
        print(f"### {it.get('title') or it.get('url')}\n{it.get('url')}\n")
        content = it.get("full_content")
        if not isinstance(content, str) or not content.strip():
            content = "\n\n".join(x for x in (it.get("excerpts") or []) if isinstance(x, str))
        print(content or "(empty)")
        print("\n---\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Parallel 检索（可多条 query 一次发）")
    s.add_argument("query", nargs="+")
    s.add_argument("-n", type=int, default=8, help="结果条数上限（1-20，默认 8）")
    s.add_argument("--objective", help="调研目标；不给则用第一条 query")
    s.add_argument("--after", help="只要该日期之后的来源，YYYY-MM-DD")
    s.add_argument("--include", help="限定域名，逗号分隔")
    s.add_argument("--exclude", help="排除域名，逗号分隔")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    e = sub.add_parser("extract", help="抓取网页正文")
    e.add_argument("urls", nargs="+")
    e.add_argument("--objective", help="抓取目标，帮 API 判断保留哪些内容")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_extract)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
