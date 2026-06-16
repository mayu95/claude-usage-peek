#!/usr/bin/env python3
"""claude-usage-peek 看门狗 — 常驻后台, 用量越过 50%/75%/90% 时弹 macOS 通知。

每隔一段时间取一次用量(优先 quota.py 的官方%, 取不到退回本地估算),
越过每个级别时各弹一次。

边沿触发: 每个级别只在"刚越过"时弹一次, 不刷屏; 跌回该级以下(如窗口重置后)
会重新武装, 下次再越过会再提醒。一次最多弹"刚越过的最高级", 避免连弹。

用法:
  python3 watch.py                       # 默认: 50/75/90 三级, 每300秒一次
  python3 watch.py --levels 60,85 --interval 600   # 自定义级别
  python3 watch.py --threshold 80        # 只用单级 80%
  python3 watch.py --once                # 只检查一次(测试/定时任务用)

后台常驻 (退出终端也继续, 日志写到文件):
  nohup python3 path/to/claude-usage-peek/watch.py >> ~/.claude-usage-watch.log 2>&1 &
停止:
  pkill -f claude-usage-peek/watch.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime

import dashboard  # 同目录; 复用 aggregate() 与 CAP_5H/CAP_7D
import quota      # 拉取官方限额%
import usage


def _as_quote(s: str) -> str:
    """转成合法的 AppleScript 双引号字符串 (转义反斜杠和双引号)。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(title: str, message: str):
    """弹一条 macOS 通知 (失败则退化为打印)。"""
    script = (f"display notification {_as_quote(message)} "
              f"with title {_as_quote(title)} sound name \"Ping\"")
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        print(f"[notify-fallback] {title}: {message}")


def check():
    """返回 (pct5, pct7, today_share, official)。
    pct5/pct7: 5h/本周窗口已用%(优先官方, 取不到退回估算)。
    today_share: 今日"不含cache"用量占周限额(CAP_7D)的百分比。"""
    try:
        quota.fetch()
    except Exception:
        pass
    lim = usage.read_limits()
    a = dashboard.aggregate()
    if lim and lim.get("util5h") is not None:
        pct5 = float(lim["util5h"]); pct7 = float(lim.get("util7d") or 0); official = True
    else:
        pct5 = a["last5h"] / dashboard.CAP_5H * 100 if dashboard.CAP_5H else 0
        pct7 = a["last7d"] / dashboard.CAP_7D * 100 if dashboard.CAP_7D else 0
        official = False
    today_share = a["today_q"] / dashboard.CAP_7D * 100 if dashboard.CAP_7D else 0
    return pct5, pct7, today_share, official


def main():
    args = sys.argv[1:]

    def opt(name, default, cast):
        if name in args:
            try:
                return cast(args[args.index(name) + 1])
            except (ValueError, IndexError):
                pass
        return default

    interval = opt("--interval", 300, int)
    once = "--once" in args
    # 多级阈值: 默认 50/75/90; 也可 --levels 50,75,90 或 --threshold 80 (单级)
    if "--threshold" in args:
        levels = [opt("--threshold", 75.0, float)]
    else:
        raw = opt("--levels", "50,75,90", str)
        try:
            levels = sorted(float(x) for x in raw.split(",") if x.strip())
        except ValueError:
            levels = [50.0, 75.0, 90.0]

    daily_alert = dashboard.DAILY_ALERT_FRAC * 100  # 今日占周限额达此% -> 弹窗 (默认40)
    state = {"5h": set(), "7d": set(), "day_done": False, "day": None}

    def run_once():
        from datetime import date
        pct5, pct7, today_share, official = check()
        src = "官方" if official else "估算"
        ts = datetime.now().astimezone().strftime("%H:%M:%S")
        lv_s = "/".join(f"{l:g}" for l in levels)
        print(f"[{ts}] {src} 5h窗口≈{pct5:.0f}%  本周窗口≈{pct7:.0f}%  "
              f"今日占周≈{today_share:.0f}%  级别 {lv_s}%", flush=True)

        # 5 小时窗口 / 本周窗口: 多级提醒 (标清是谁的比例)
        for key, pct, label in (("5h", pct5, "5 小时窗口"), ("7d", pct7, "本周窗口")):
            done = state[key]
            for lv in list(done):
                if pct < lv:
                    done.discard(lv)
            crossed = [lv for lv in levels if pct >= lv and lv not in done]
            if crossed:
                top = max(crossed)
                notify("⚠️ Claude 用量提醒",
                       f"{label} {src}已用 {pct:.0f}% (超过 {top:g}%)")
                done.update(crossed)

        # 今日单日: 占周限额达 40% (=2倍日均) 弹一次, 跨天重置
        td = date.today()
        if state["day"] != td:
            state["day"] = td
            state["day_done"] = False
        if today_share >= daily_alert and not state["day_done"]:
            notify("⚠️ Claude 今日用量提醒",
                   f"今日已用 = 本周额度的 {today_share:.0f}% (日均目标约 20%, 已超 2 倍)")
            state["day_done"] = True

    if once:
        run_once()
        return

    print(f"看门狗启动: 阈值 {'/'.join(f'{l:g}' for l in levels)}%, "
          f"每 {interval} 秒检查一次。Ctrl+C 退出。", flush=True)
    try:
        while True:
            run_once()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
