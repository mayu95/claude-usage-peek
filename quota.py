#!/usr/bin/env python3
"""claude-usage-peek 官方额度拉取 — 取 Anthropic 真实 5h/7d 限额使用率。

原理: 用你本机 Claude Code 的登录令牌, 向 api.anthropic.com 发一个最小请求,
读响应头里的 anthropic-ratelimit-unified-* (官方算的真实百分比和重置时间)。

安全:
  - 令牌只来自你本机 (macOS 钥匙串 或 ~/.claude/.credentials.json);
  - 只发给 api.anthropic.com (官方), 不经任何第三方; 令牌不落盘、不打印;
  - 缓存文件只存百分比/重置时间, 不存令牌。

用法:
  python3 quota.py          # 拉取并打印官方 5h/7d%, 同时写入缓存
  python3 quota.py --quiet  # 只刷新缓存, 不打印 (供看板/定时调用)

缓存写到: ~/.claude/usage-peek-quota.json (供 usage.py / dashboard.py 读取)
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path.home() / ".claude" / "usage-peek-quota.json"
CRED_FILE = Path.home() / ".claude" / ".credentials.json"
API = "https://api.anthropic.com/v1/messages"
PROBE_MODEL = "claude-haiku-4-5-20251001"  # 最便宜, max_tokens=1, 几乎不耗额度


def _get_token() -> str | None:
    """从本机凭据取 OAuth accessToken。先文件后钥匙串。不打印、不返回给外部。"""
    # 1) ~/.claude/.credentials.json (Linux / 部分配置)
    try:
        d = json.loads(CRED_FILE.read_text())
        t = (d.get("claudeAiOauth") or {}).get("accessToken")
        if t:
            return t
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    # 2) macOS 钥匙串
    try:
        raw = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if raw:
            return json.loads(raw)["claudeAiOauth"]["accessToken"]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError):
        pass
    return None


def fetch() -> dict | None:
    """请求 Anthropic, 解析 ratelimit 头。成功返回 dict 并写缓存; 失败返回 None。"""
    tok = _get_token()
    if not tok:
        return None

    body = json.dumps({
        "model": PROBE_MODEL,
        "max_tokens": 1,
        "system": "You are Claude Code, Anthropic's official CLI for Claude.",
        "messages": [{"role": "user", "content": "."}],
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST")
    req.add_header("authorization", f"Bearer {tok}")
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("anthropic-beta", "oauth-2025-04-20")
    req.add_header("content-type", "application/json")

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        headers = resp.headers
    except urllib.error.HTTPError as e:
        headers = e.headers  # 限额头在错误响应里通常也有
    except (urllib.error.URLError, OSError):
        return None

    def hf(name):  # header float
        v = headers.get(name)
        try:
            return float(v) if v is not None else None
        except ValueError:
            return None

    def hi(name):  # header int
        v = headers.get(name)
        try:
            return int(v) if v is not None else None
        except ValueError:
            return None

    u5 = hf("anthropic-ratelimit-unified-5h-utilization")
    u7 = hf("anthropic-ratelimit-unified-7d-utilization")
    if u5 is None and u7 is None:
        return None  # 没拿到限额头, 视为失败

    out = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "usageData": {
            # 存成百分比 (头里是 0~1 的小数)
            "utilization5h": round(u5 * 100, 1) if u5 is not None else None,
            "utilization7d": round(u7 * 100, 1) if u7 is not None else None,
            "reset5hAt": hi("anthropic-ratelimit-unified-5h-reset"),
            "reset7dAt": hi("anthropic-ratelimit-unified-7d-reset"),
            "limitStatus": headers.get("anthropic-ratelimit-unified-status"),
        },
    }
    try:
        CACHE.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    except OSError:
        pass
    return out


def main():
    quiet = "--quiet" in sys.argv[1:]
    data = fetch()
    if not data:
        if not quiet:
            print("拉取失败: 取不到令牌或请求出错 (令牌可能已过期, 重开 Claude Code 登录一次)。")
        sys.exit(1)
    if quiet:
        return
    u = data["usageData"]
    def fmt_reset(ts):
        if not ts:
            return ""
        return datetime.fromtimestamp(ts).astimezone().strftime("%m-%d %H:%M")
    print("官方实时额度 (来自 Anthropic 响应头):")
    print(f"  5 小时窗口: 已用 {u['utilization5h']}%  · 重置 {fmt_reset(u['reset5hAt'])}")
    print(f"  7 天窗口:   已用 {u['utilization7d']}%  · 重置 {fmt_reset(u['reset7dAt'])}")
    print(f"  状态: {u['limitStatus']}  · 已写入 {CACHE}")


if __name__ == "__main__":
    main()
