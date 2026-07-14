#!/usr/bin/env python3
"""claude-usage-peek 官方额度拉取 — 取 Anthropic 真实 5h/7d(及某模型周限额)使用率。

原理: 用你本机 Claude Code 的登录令牌, GET api.anthropic.com/api/oauth/usage
(Claude Code /status 用的同一个官方接口, 纯读取、不消耗额度), 拿到 5 小时 / 7 天
以及"按模型的周限额"(如 Fable)的已用百分比与重置时间。

安全:
  - 令牌只来自你本机 (macOS 钥匙串 或 ~/.claude/.credentials.json);
  - 只发给 api.anthropic.com (官方), 不经任何第三方; 令牌不落盘、不打印;
  - 缓存文件只存百分比/重置时间/套餐名, 不存令牌、不存对话内容。

用法:
  python3 quota.py          # 拉取并打印官方 5h/7d(+模型周限额)%, 同时写入缓存
  python3 quota.py --quiet  # 只刷新缓存, 不打印 (供看板/定时调用)

缓存写到: ~/.claude/usage-peek-quota.json (供 usage.py / dashboard.py 读取)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path.home() / ".claude" / "usage-peek-quota.json"
CRED_FILE = Path.home() / ".claude" / ".credentials.json"
USAGE_API = "https://api.anthropic.com/api/oauth/usage"  # Claude Code /status 的官方用量接口


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


def _iso_to_epoch(s):
    """ISO 时间字符串 -> epoch 秒 (int)。失败返回 None。"""
    if not s:
        return None
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except (ValueError, TypeError):
        return None


def _scoped_from(data):
    """从 /api/oauth/usage 的响应里取 kind==weekly_scoped 的限额(某模型的周限额, 如 Fable)。
    标签取自 API 的 scope.model.display_name —— 模型改名时会自动跟随。
    返回 {"label", "utilization", "resetAt"} 或 None。"""
    for lim in data.get("limits") or []:
        if lim.get("kind") == "weekly_scoped" and lim.get("percent") is not None:
            model = (lim.get("scope") or {}).get("model") or {}
            return {
                "label": model.get("display_name"),
                "utilization": float(lim["percent"]),
                "resetAt": _iso_to_epoch(lim.get("resets_at")),
            }
    return None


def fetch() -> dict | None:
    """GET /api/oauth/usage, 解析 5h/7d 及模型周限额。成功返回 dict 并写缓存; 失败返回 None。"""
    tok = _get_token()
    if not tok:
        return None

    req = urllib.request.Request(USAGE_API, method="GET")
    req.add_header("authorization", f"Bearer {tok}")
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("anthropic-beta", "oauth-2025-04-20")
    req.add_header("accept", "application/json")
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None

    fh = data.get("five_hour") or {}
    sd = data.get("seven_day") or {}
    u5 = fh.get("utilization")
    u7 = sd.get("utilization")
    if u5 is None and u7 is None:
        return None  # 接口没给用量, 视为失败

    # 状态: limits 里出现的第一个非 normal 的 severity; 都正常则 allowed
    status = "allowed"
    for lim in data.get("limits") or []:
        sev = lim.get("severity")
        if sev and sev != "normal":
            status = sev
            break

    out = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "usageData": {
            # 接口给的已用百分比本身就是 0~100
            "utilization5h": round(float(u5), 1) if u5 is not None else None,
            "utilization7d": round(float(u7), 1) if u7 is not None else None,
            "reset5hAt": _iso_to_epoch(fh.get("resets_at")),
            "reset7dAt": _iso_to_epoch(sd.get("resets_at")),
            "limitStatus": status,
        },
        # 某模型的周限额(如 Fable); 账号没有则 None
        "scopedWeekly": _scoped_from(data),
    }
    _write_cache(out)
    return out


def _write_cache(out: dict):
    """原子写缓存: 先写同目录临时文件再 os.replace, 并发读者永远只会看到完整 JSON。"""
    try:
        tmp = CACHE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        os.replace(tmp, CACHE)
    except OSError:
        pass


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
    print("官方实时额度 (来自 /api/oauth/usage):")
    print(f"  5 小时窗口: 已用 {u['utilization5h']}%  · 重置 {fmt_reset(u['reset5hAt'])}")
    print(f"  7 天窗口:   已用 {u['utilization7d']}%  · 重置 {fmt_reset(u['reset7dAt'])}")
    sw = data.get("scopedWeekly")
    if sw:
        print(f"  {sw.get('label') or '模型'} 周限额: 已用 {sw['utilization']:g}%  · 重置 {fmt_reset(sw.get('resetAt'))}")
    print(f"  状态: {u['limitStatus']}  · 已写入 {CACHE}")


if __name__ == "__main__":
    main()
