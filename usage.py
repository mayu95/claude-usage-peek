#!/usr/bin/env python3
"""claude-usage-peek — Claude Code 本地用量统计。

零依赖、纯读本地文件、不联网。

两种用法:
  1) statusline:  Claude Code 通过 stdin 传入当前会话的 JSON，本脚本打印一行
                  "模型 · 本会话上下文 · 今日 token" 到 stdout。
  2) CLI:         直接在终端运行 `python3 usage.py` 打印明细
                  (按天 / 按模型的 token 汇总)。加 --json 输出原始数据。

数据来源: ~/.claude/projects/**/*.jsonl 里每条 assistant 消息的 message.usage。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
# 我们自己用 quota.py 拉取官方限额后写的缓存 (不再依赖任何第三方插件)
LIMIT_CACHE = Path.home() / ".claude" / "usage-peek-quota.json"


def _humanize(n: int) -> str:
    """1234 -> 1.2k, 8400000 -> 8.4M"""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return f"{n / 1_000_000:.1f}M".replace(".0M", "M")


def _msg_total(usage: dict) -> int:
    """一条消息处理的全部 token (含 cache)。"""
    return (
        int(usage.get("input_tokens", 0) or 0)
        + int(usage.get("cache_creation_input_tokens", 0) or 0)
        + int(usage.get("cache_read_input_tokens", 0) or 0)
        + int(usage.get("output_tokens", 0) or 0)
    )


def iter_assistant_records(paths):
    """逐行解析 transcript，产出 (timestamp, model, usage, message_id, session_id)。
    用 message_id 去重，避免重试/重放被重复计数。
    去重集合按"单个文件"维度，每个文件处理完即释放——这样内存只与最大单文件
    成正比、与历史总量无关(封顶);重试/重放都在同一 transcript 内,不影响准确性。"""
    for p in paths:
        seen = set()
        try:
            with open(p, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or '"usage"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") != "assistant":
                        continue
                    msg = rec.get("message") or {}
                    usage = msg.get("usage")
                    if not usage:
                        continue
                    mid = msg.get("id")
                    if mid and mid in seen:
                        continue
                    if mid:
                        seen.add(mid)
                    yield (
                        rec.get("timestamp"),
                        msg.get("model", "unknown"),
                        usage,
                        mid,
                        rec.get("sessionId"),
                    )
        except (OSError, UnicodeDecodeError):
            continue


def all_transcripts():
    if not PROJECTS_DIR.exists():
        return []
    return sorted(PROJECTS_DIR.rglob("*.jsonl"))


def local_date(ts: str):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date()


def read_limits():
    """读取官方限额使用率(由 quota.py 拉取 Anthropic 响应头后写入的缓存)。
    返回 dict 或 None。无网络/未取令牌时缓存可能不存在。
    字段: util5h/util7d (已用百分比), reset5h/reset7d (本地 datetime), status, updated。"""
    try:
        data = json.loads(LIMIT_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    u = data.get("usageData") or {}
    if not u:
        return None

    def _ts(key):
        v = u.get(key)
        if not v:
            return None
        try:
            return datetime.fromtimestamp(int(v)).astimezone()
        except (ValueError, OSError, OverflowError):
            return None

    updated = None
    ua = data.get("updatedAt")
    if ua:
        try:
            updated = datetime.fromisoformat(ua.replace("Z", "+00:00")).astimezone()
        except ValueError:
            updated = None

    return {
        "util5h": u.get("utilization5h"),
        "util7d": u.get("utilization7d"),
        "reset5h": _ts("reset5hAt"),
        "reset7d": _ts("reset7dAt"),
        "status": u.get("limitStatus"),
        "updated": updated,
    }


def _fmt_remaining(util, reset, now):
    """'余 100% (重置 14:00)' 之类。util 为已用百分比。"""
    if util is None:
        return None
    remaining = max(0, 100 - util)
    s = f"余 {remaining:g}%"
    if reset and reset > now:
        # 同一天显示时分，否则显示月-日 时分
        if reset.date() == now.date():
            s += f" (重置 {reset:%H:%M})"
        else:
            s += f" (重置 {reset:%m-%d %H:%M})"
    return s


def collect():
    """汇总所有记录。返回 (per_day, per_model, records)。"""
    per_day = {}    # date -> total tokens
    per_model = {}  # model -> total tokens
    records = []
    for ts, model, usage, mid, sid in iter_assistant_records(all_transcripts()):
        tot = _msg_total(usage)
        d = local_date(ts)
        if d is not None:
            per_day[d] = per_day.get(d, 0) + tot
        per_model[model] = per_model.get(model, 0) + tot
        records.append((ts, model, usage, mid, sid))
    return per_day, per_model, records


# ---------------------------------------------------------------------------
# statusline 模式
# ---------------------------------------------------------------------------

def run_statusline(stdin_data: dict):
    model_name = None
    m = stdin_data.get("model")
    if isinstance(m, dict):
        model_name = m.get("display_name") or m.get("id")
    transcript_path = stdin_data.get("transcript_path")

    today = datetime.now().astimezone().date()
    week_start = today - timedelta(days=today.weekday())  # 本周一

    # 一次遍历所有 transcript: 累加今日 / 本周 / 本月
    today_total = week_total = month_total = 0
    for ts, _model, usage, _mid, _sid in iter_assistant_records(all_transcripts()):
        d = local_date(ts)
        if d is None:
            continue
        tot = _msg_total(usage)
        if d == today:
            today_total += tot
        if d >= week_start:
            week_total += tot
        if d.year == today.year and d.month == today.month:
            month_total += tot

    # 本会话累计 token (整个 transcript 的总量)
    session_total = 0
    if transcript_path and os.path.exists(transcript_path):
        for _ts, _model, usage, _mid, _sid in iter_assistant_records([transcript_path]):
            session_total += _msg_total(usage)

    parts = []
    if model_name:
        parts.append(f"⊙ {model_name}")
    if session_total:
        parts.append(f"本会话 {_humanize(session_total)}")
    parts.append(f"今日 {_humanize(today_total)}")
    parts.append(f"本周 {_humanize(week_total)}")
    parts.append(f"本月 {_humanize(month_total)} tok")

    # 剩余额度 (5h / 7d 限额窗口)
    lim = read_limits()
    if lim:
        now = datetime.now().astimezone()
        r5 = _fmt_remaining(lim["util5h"], lim["reset5h"], now)
        r7 = _fmt_remaining(lim["util7d"], lim["reset7d"], now)
        if r5:
            parts.append(f"5h {r5}")
        if r7:
            parts.append(f"7d {r7}")

    sys.stdout.write(" · ".join(parts))


# ---------------------------------------------------------------------------
# CLI 模式
# ---------------------------------------------------------------------------

def run_cli(as_json: bool):
    per_day, per_model, records = collect()

    if as_json:
        out = {
            "per_day": {str(k): v for k, v in sorted(per_day.items())},
            "per_model": per_model,
            "total_tokens": sum(per_model.values()),
            "messages": len(records),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    total = sum(per_model.values())
    print("Claude Code 本地用量 (token, 含 cache)")
    print("=" * 40)
    print(f"总计: {_humanize(total)} tok  ({total:,})  · {len(records)} 条消息\n")

    lim = read_limits()
    if lim:
        now = datetime.now().astimezone()
        r5 = _fmt_remaining(lim["util5h"], lim["reset5h"], now)
        r7 = _fmt_remaining(lim["util7d"], lim["reset7d"], now)
        print("剩余额度:")
        if r5:
            print(f"  5 小时窗口  {r5}")
        if r7:
            print(f"  7 天窗口    {r7}")
        print()

    print("按天 (最近 14 天):")
    for d in sorted(per_day.keys(), reverse=True)[:14]:
        bar = "█" * min(40, max(1, per_day[d] * 40 // max(total, 1)))
        print(f"  {d}  {_humanize(per_day[d]):>7}  {bar}")

    print("\n按模型:")
    for model, tok in sorted(per_model.items(), key=lambda x: -x[1]):
        if tok == 0:  # <synthetic> 等占位消息
            continue
        print(f"  {model:<24} {_humanize(tok):>7}  ({tok:,})")


def main():
    args = sys.argv[1:]
    # 有 stdin 管道输入 (statusline) 且不是 TTY -> statusline 模式
    if not sys.stdin.isatty() and "--cli" not in args:
        raw = sys.stdin.read()
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            data = {}
        run_statusline(data)
        return
    run_cli(as_json="--json" in args)


if __name__ == "__main__":
    main()
