#!/usr/bin/env python3
"""claude-usage-peek 看板 — 生成自包含 HTML 用量看板 (含 GitHub 式热力图)。

纯 HTML + CSS，无 JavaScript、无 CDN、不联网。复用 usage.py 的本地解析。

用法:
  python3 dashboard.py            # 生成 dashboard.html 并自动用浏览器打开
  python3 dashboard.py --no-open  # 只生成文件, 不打开
  python3 dashboard.py -o ~/x.html  # 指定输出路径
  python3 dashboard.py --serve    # 起本地实时看板 (http://127.0.0.1:8787, 每60秒自刷新)
  python3 dashboard.py --serve --port 9000
"""
from __future__ import annotations

import html
import math
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import usage  # 同目录, Python 会把脚本所在目录加入 sys.path
import quota  # 拉取官方限额%

OUT_DEFAULT = Path(__file__).resolve().parent / "dashboard.html"
QUOTA_TTL = 300  # 官方额度缓存超过这么多秒(5分钟)才刷新一次, 避免频繁打 API

# ---------------------------------------------------------------------------
# 多语言 (en / zh / ja) — 与菜单栏 app 一致, 默认英文。
# 语言来源: 命令行 --lang, 或菜单栏 app 的设置 (defaults), 否则 en。
# ---------------------------------------------------------------------------
LANG = "en"

WD = {
    "zh": ["一", "二", "三", "四", "五", "六", "日"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "ja": ["月", "火", "水", "木", "金", "土", "日"],
}

T = {
    "title":      {"en": "Claude Code Usage", "zh": "Claude Code 用量看板", "ja": "Claude Code 使用量ダッシュボード"},
    "h1":         {"en": "🤖 Claude Code Usage", "zh": "🤖 Claude Code 用量看板", "ja": "🤖 Claude Code 使用量ダッシュボード"},
    "sub_main":   {"en": "Local data · generated {date} · {msgs} messages · {tot} tok total · browser refresh = update official quota now, otherwise every 5 min",
                   "zh": "本地数据 · 生成于 {date} · 共 {msgs} 条消息 · 累计 {tot} tok · 点浏览器刷新=立即更新官方额度，否则每5分钟",
                   "ja": "ローカルデータ · 生成 {date} · {msgs} 件のメッセージ · 累計 {tot} tok · ブラウザ更新＝公式上限を即更新、それ以外は5分ごと"},
    "card_today": {"en": "Today", "zh": "今日 token", "ja": "今日"},
    "card_week":  {"en": "This week", "zh": "本周 token", "ja": "今週"},
    "card_month": {"en": "This month", "zh": "本月 token", "ja": "今月"},
    "card_total": {"en": "All-time", "zh": "累计 token", "ja": "累計"},
    "cards_note": {"en": "↑ These cards are <b>total processed volume (incl. cache reads)</b> — large. The limit-relevant \"excluding cache\" usage is in the quota panel below.",
                   "zh": "↑ 这几张卡片是<b>总处理量(含 cache 读取)</b>，体量大；与限额相关的「不含 cache」用量见下方额度面板。",
                   "ja": "↑ これらのカードは<b>総処理量（キャッシュ読み取り含む）</b>で大きめ。上限に関わる「キャッシュ除外」使用量は下の上限パネルを参照。"},
    "panel_quota":    {"en": "Quota / recent usage", "zh": "额度 / 近期用量", "ja": "上限 / 最近の使用量"},
    "panel_heatmap":  {"en": "Daily usage heatmap (since first use, up to a year)", "zh": "每日用量热力图 (自首次使用起, 最多回看一年)", "ja": "日次使用量ヒートマップ（初回使用以降・最大1年）"},
    "panel_monthly":  {"en": "Daily usage this month ({ym}) · red = over daily budget (20% of weekly limit)", "zh": "本月每日用量 ({ym}) · 红柱=当日超日预期(周限额20%)", "ja": "今月の日次使用量（{ym}）· 赤＝日次目安超過（週上限の20%）"},
    "panel_hourly":   {"en": "Usage by hour (all dates combined · not just today)", "zh": "各时段用量 (所有日期累计 · 非今日)", "ja": "時間帯別使用量（全期間合算・当日のみではない）"},
    "panel_models":   {"en": "By model", "zh": "按模型", "ja": "モデル別"},
    "panel_breakdown": {"en": "Token breakdown", "zh": "Token 分项", "ja": "トークン内訳"},
    "comp_input":        {"en": "input", "zh": "输入 input", "ja": "入力 input"},
    "comp_output":       {"en": "output", "zh": "输出 output", "ja": "出力 output"},
    "comp_cache_read":   {"en": "cache read", "zh": "缓存读 cache read", "ja": "キャッシュ読取 cache read"},
    "comp_cache_create": {"en": "cache create", "zh": "缓存写 cache create", "ja": "キャッシュ作成 cache create"},
    "hm_nodata":  {"en": "No usage data yet", "zh": "还没有用量数据", "ja": "使用量データがまだありません"},
    "hm_less":    {"en": "Less", "zh": "少", "ja": "少"},
    "hm_more":    {"en": "More", "zh": "多", "ja": "多"},
    "hm_caption": {"en": "{start} → {today} · {n} days with usage", "zh": "{start} → {today} · {n} 天有用量", "ja": "{start} → {today} · 使用 {n} 日"},
    "live_prefix": {"en": "Live local stats (incl. cache, processed):", "zh": "本机实时统计 (含 cache, 处理量):", "ja": "ローカル実測（キャッシュ含む・処理量）:"},
    "live_today": {"en": "Today", "zh": "今日", "ja": "今日"},
    "live_5h":    {"en": "Last 5 hours", "zh": "最近 5 小时", "ja": "直近5時間"},
    "live_7d":    {"en": "Last 7 days", "zh": "最近 7 天", "ja": "直近7日"},
    "win_5h":     {"en": "5-hour window", "zh": "5 小时窗口", "ja": "5時間ウィンドウ"},
    "win_7d":     {"en": "7-day window", "zh": "7 天窗口", "ja": "7日間ウィンドウ"},
    "q_official": {"en": "official, used {pct}%", "zh": "官方 已用 {pct}%", "ja": "公式 使用 {pct}%"},
    "q_estimate": {"en": "estimate ~{pct}% (cap {cap})", "zh": "估算 ~{pct}% (上限 {cap})", "ja": "推定 ~{pct}%（上限 {cap}）"},
    "q_reset_in": {"en": " · resets in {dur}", "zh": " · 还有 {dur} 重置", "ja": " · あと {dur} でリセット"},
    "q_pace":     {"en": " · ≈ {pct}% by reset at this rate", "zh": " · 按此速度到时约 {pct}%", "ja": " · この調子だとリセット時に約 {pct}%"},
    "q_updated":  {"en": ", updated {t}", "zh": "，更新于 {t}", "ja": "、更新 {t}"},
    "q_note_official": {"en": "The bars are <b>Anthropic official live data</b> (read from response headers by quota.py{upd}), only api.anthropic.com, no third party. The dashboard auto-refreshes every {min} min (tune QUOTA_TTL at the top of dashboard.py).",
                        "zh": "进度条为 <b>Anthropic 官方实时数据</b>(由 quota.py 读响应头{upd})，只连 api.anthropic.com、不经第三方。看板每 {min} 分钟自动刷新一次(改 dashboard.py 顶部 QUOTA_TTL 可调)。",
                        "ja": "バーは <b>Anthropic 公式リアルタイムデータ</b>（quota.py がレスポンスヘッダーから取得{upd}）。api.anthropic.com のみ・第三者を経由しません。{min} 分ごとに自動更新（dashboard.py 冒頭の QUOTA_TTL で調整）。"},
    "q_note_estimate": {"en": "Showing a <b>local estimate</b> (official data unavailable). Run <code>python3 quota.py</code> to fetch official % (needs a valid login token); if expired, sign in to Claude Code once.",
                        "zh": "当前显示<b>本地估算</b>(官方数据未取到)。运行 <code>python3 quota.py</code> 拉取官方%(需登录令牌有效)；令牌过期时重开一次 Claude Code 登录即可。",
                        "ja": "<b>ローカル推定</b>を表示中（公式データ未取得）。<code>python3 quota.py</code> で公式%を取得（有効なログイントークンが必要）。期限切れなら Claude Code に再ログイン。"},
    "over_flag":  {"en": "  ⚠ over daily budget", "zh": "  ⚠超日预期", "ja": "  ⚠日次目安超過"},
    "mon_tip":    {"en": "{date} ({wd})  volume {v} · limit-relevant {vq} tok{flag}", "zh": "{date} (周{wd})  体量 {v} · 限额相关 {vq} tok{flag}", "ja": "{date}（{wd}）  処理量 {v} · 上限関連 {vq} tok{flag}"},
}


def t(key, **kw):
    s = T.get(key, {}).get(LANG) or T.get(key, {}).get("en") or key
    return s.format(**kw) if kw else s


def _wd(i):
    return WD.get(LANG, WD["en"])[i]


def _detect_lang(args):
    """优先 --lang; 否则读菜单栏 app 的语言设置 (macOS defaults); 都没有则 en。"""
    if "--lang" in args:
        try:
            v = args[args.index("--lang") + 1]
            if v in ("en", "zh", "ja"):
                return v
        except IndexError:
            pass
    try:
        v = subprocess.run(
            ["defaults", "read", "local.claude-usage-peek.menubar", "lang"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        if v in ("en", "zh", "ja"):
            return v
    except (OSError, subprocess.SubprocessError):
        pass
    return "en"


def _refresh_quota(force=False):
    """渲染前best-effort刷新官方额度。force=True 立即刷新(手动点刷新时);
    否则只在缓存超过 QUOTA_TTL 秒才刷新。出错(无网/无令牌)就用旧缓存。"""
    if not force:
        try:
            age = time.time() - os.path.getmtime(quota.CACHE)
        except OSError:
            age = 1e9
        if age <= QUOTA_TTL:
            return
    try:
        quota.fetch()
    except Exception:
        pass

# --- 限额上限估算 (token, 不含 cache 读取) ----------------------------------
# 真实限额% 本地拿不到。这里用"官网看到的已用% + 本机近期 token(不含cache读取)"
# 反推一个上限, 让进度条能动、给出估算 %。
# 重要: 基准是"不含 cache 读取"的 token (input+output+cache_creation), 因为
#       cache 读取几乎不计入限额, 用总量会严重高估、导致每次校准都飘。
# 如何重新校准:
#   1) 打开 claude.ai 看当前 5h / 7d 各用了百分之几;
#   2) 看本看板"最近 5 小时 / 最近 7 天"的 token 数 N (已是不含cache读取口径);
#   3) 上限 ≈ N ÷ (该百分比). 例: 最近5h=804k、官网13% -> CAP_5H≈6.2M.
# 默认值按 2026-06-16 读数校准, 偏保守 (5h:840k/14.5%, 7d:1.9M/2.5%)。
CAP_5H = 5_800_000        # ~5.8M token / 5 小时 (不含 cache 读取)
CAP_7D = 77_600_000       # ~77.6M token / 7 天 (不含 cache 读取)
# 日预期 = 周限额的多少 (5 个工作日均摊 -> 每天 20%); 某天超过则在月图标红
EXPECTED_DAILY_FRAC = 0.20
DAILY_ALERT_FRAC = 0.40   # 某天用掉周限额这么多就弹窗 (= 2 倍日均)


# ---------------------------------------------------------------------------
# 数据聚合
# ---------------------------------------------------------------------------

def _local_dt(ts: str):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def aggregate():
    per_day = {}          # date -> total token (含 cache, 体量)
    per_day_q = {}        # date -> 不含 cache 读取的 token (限额相关)
    per_model = {}        # model -> total token
    per_hour = [0] * 24   # 小时 -> total token
    comp = {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}
    msg_count = 0

    now = datetime.now().astimezone()
    today = now.date()
    cut5h = now - timedelta(hours=5)    # 最近 5 小时 (滚动窗口)
    cut7d = now - timedelta(days=7)     # 最近 7 天 (滚动窗口)
    last5h = last7d = today_q = 0           # 不含 cache 读取 (估算/限额相关)
    last5h_incl = last7d_incl = 0           # 含 cache (展示用)

    for ts, model, u, _mid, _sid in usage.iter_assistant_records(usage.all_transcripts()):
        tot = usage._msg_total(u)
        inp = int(u.get("input_tokens", 0) or 0)
        out = int(u.get("output_tokens", 0) or 0)
        cre = int(u.get("cache_creation_input_tokens", 0) or 0)
        # 额度估算基准: 不含 cache 读取 (cache 读取几乎不计入限额, 会严重灌水)
        qtot = inp + out + cre
        per_model[model] = per_model.get(model, 0) + tot
        comp["input"] += inp
        comp["output"] += out
        comp["cache_read"] += int(u.get("cache_read_input_tokens", 0) or 0)
        comp["cache_create"] += cre
        dt = _local_dt(ts)
        if dt is not None:
            d = dt.date()
            per_day[d] = per_day.get(d, 0) + tot
            per_day_q[d] = per_day_q.get(d, 0) + qtot
            per_hour[dt.hour] += tot
            if dt >= cut5h:
                last5h += qtot
                last5h_incl += tot
            if dt >= cut7d:
                last7d += qtot
                last7d_incl += tot
            if d == today:
                today_q += qtot
        msg_count += 1

    week_start = today - timedelta(days=today.weekday())
    today_total = per_day.get(today, 0)
    week_total = sum(v for d, v in per_day.items() if d >= week_start)
    month_total = sum(
        v for d, v in per_day.items()
        if d.year == today.year and d.month == today.month
    )

    return {
        "per_day": per_day,
        "per_model": per_model,
        "per_hour": per_hour,
        "comp": comp,
        "msg_count": msg_count,
        "total": sum(per_model.values()),
        "today": today_total,
        "week": week_total,
        "month": month_total,
        "last5h": last5h,
        "last7d": last7d,
        "today_q": today_q,
        "per_day_q": per_day_q,
        "last5h_incl": last5h_incl,
        "last7d_incl": last7d_incl,
    }


# ---------------------------------------------------------------------------
# HTML 片段
# ---------------------------------------------------------------------------

WEEKS = 53  # 最多回看 53 周 (约一年); 不足一年则从首次使用日开始


def _level_fn(values):
    """对数配色: 把每日用量映射到 4 档 (1..4), 0 表示无用量。
    在 [最小非零, 最大] 之间做对数归一化 —— 越大越深, 既体现量级差异,
    又不会被某个异常大的一天把其它天全压成最浅。"""
    s = [v for v in values if v > 0]
    if not s:
        return lambda v: 0
    lo, hi = math.log(min(s) + 1), math.log(max(s) + 1)
    span = hi - lo

    def level(v):
        if v <= 0:
            return 0
        if span <= 0:           # 只有一种数值
            return 4
        frac = (math.log(v + 1) - lo) / span      # 0..1
        return max(1, min(4, math.ceil(frac * 4)))

    return level


def build_heatmap(per_day) -> str:
    today = datetime.now().astimezone().date()
    used = {d: v for d, v in per_day.items() if v > 0}
    if not used:
        return f'<div class="muted">{t("hm_nodata")}</div>'

    # 起点 = max(一年前, 首次使用日), 再对齐到所在周的"周日" (GitHub 风格)
    def to_sunday(d):
        return d - timedelta(days=(d.weekday() + 1) % 7)

    earliest = to_sunday(today - timedelta(weeks=WEEKS - 1))
    first_use = min(used)
    start = to_sunday(max(earliest, first_use))
    total_days = (today - start).days + 1

    # 色阶只按"被显示出来的使用日"计算分位数
    level = _level_fn(v for d, v in used.items() if d >= start)

    # 按列(周)分组
    columns = [[] for _ in range((total_days + 6) // 7 + 1)]
    month_at_col = {}
    for i in range(total_days):
        d = start + timedelta(days=i)
        col = (d - start).days // 7
        v = per_day.get(d, 0)
        columns[col].append((d, v))
        if d.day <= 7 and d.weekday() == 6:  # 该月第一个周日 -> 标月份
            month_at_col[col] = d.strftime("%b")

    # 月份标签行
    month_cells = []
    for col in range(len(columns)):
        label = month_at_col.get(col, "")
        month_cells.append(f'<div class="hm-month">{label}</div>')
    month_row = f'<div class="hm-months">{"".join(month_cells)}</div>'

    # 列
    col_html = []
    for col_days in columns:
        cells = []
        # 补齐到 7 行 (首列可能不是从周一开始, 但我们已对齐到周一)
        for d, v in col_days:
            lvl = level(v)
            tip = f"{d.isoformat()} ({_wd(d.weekday())}): {usage._humanize(v)} tok" if v else f"{d.isoformat()}: 0"
            cells.append(f'<div class="hm-cell lvl{lvl}" title="{html.escape(tip)}"></div>')
        col_html.append(f'<div class="hm-col">{"".join(cells)}</div>')

    legend = (
        f'<div class="hm-legend">{t("hm_less")}'
        + "".join(f'<div class="hm-cell lvl{l}"></div>' for l in range(5))
        + f'{t("hm_more")}</div>'
    )
    caption = (f'<div class="hm-cap muted">'
               f'{t("hm_caption", start=start.isoformat(), today=today.isoformat(), n=len(used))}</div>')
    return (
        '<div class="heatmap">'
        + month_row
        + f'<div class="hm-grid">{"".join(col_html)}</div>'
        + legend
        + caption
        + "</div>"
    )


def _bar_chart(items) -> str:
    """items: (axis_label, value, tooltip) 或 (axis_label, value, tooltip, over)。
    over=True 时该柱标红(超预期)。数字标在每根柱顶部。"""
    vmax = max((it[1] for it in items), default=0)
    cols = []
    for it in items:
        lab, v, tip = it[0], it[1], it[2]
        over = it[3] if len(it) > 3 else False
        pct = (v / vmax * 100) if vmax else 0
        num = usage._humanize(v) if v else ""
        cls = "bbar over" if over else "bbar"
        cols.append(
            f'<div class="bcol" title="{html.escape(tip)}">'
            f'<div class="bnum">{num}</div>'
            f'<div class="{cls}" style="height:{pct:.1f}%"></div>'
            f'<div class="blbl">{lab}</div>'
            "</div>"
        )
    return f'<div class="bars">{"".join(cols)}</div>'


def build_hourly(per_hour) -> str:
    items = [
        (str(h) if h % 3 == 0 else "", per_hour[h], f"{h:02d}:00  {usage._humanize(per_hour[h])} tok")
        for h in range(24)
    ]
    return _bar_chart(items)


def build_monthly(per_day, per_day_q) -> str:
    """本月 1 号到今天, 每天一根柱。柱高=含cache体量; 当日"不含cache"用量超过
    日预期(周限额 CAP_7D 的 20%)时, 该柱标红。"""
    today = datetime.now().astimezone().date()
    daily_budget = CAP_7D * EXPECTED_DAILY_FRAC if CAP_7D else 0  # 不含cache的日预期
    items = []
    for day in range(1, today.day + 1):
        d = today.replace(day=day)
        v = per_day.get(d, 0)
        vq = per_day_q.get(d, 0)
        over = bool(daily_budget and vq > daily_budget)
        lab = str(day) if (day == 1 or day % 5 == 0 or day == today.day) else ""
        wdl = ("周" if LANG == "zh" else "") + _wd(d.weekday())
        flag = t("over_flag") if over else ""
        tip = t("mon_tip", date=d.isoformat(), wd=wdl,
                v=usage._humanize(v), vq=usage._humanize(vq), flag=flag)
        items.append((lab, v, tip, over))
    return _bar_chart(items)


def _fmt_dur(td) -> str:
    """timedelta -> '2小时18分' / '1天3小时' / '12分'。"""
    secs = int(td.total_seconds())
    if secs < 0:
        secs = 0
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if LANG == "zh":
        if days:
            return f"{days}天{hours}小时"
        if hours:
            return f"{hours}小时{mins}分"
        return f"{mins}分"
    if LANG == "ja":
        if days:
            return f"{days}日{hours}時間"
        if hours:
            return f"{hours}時間{mins}分"
        return f"{mins}分"
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def build_quota(a) -> str:
    now = datetime.now().astimezone()
    h = usage._humanize
    lim = usage.read_limits()
    last5h, last7d = a["last5h"], a["last7d"]  # 不含 cache, 估算兜底用

    # (1) 本机实时统计: 今日 / 最近 5 小时 / 最近 7 天 处理量 (含 cache)
    live = (
        f'<div class="quota-live">{t("live_prefix")}'
        f'<span class="lv">{t("live_today")} <b>{h(a["today"])}</b> tok</span>'
        f'<span class="lv">{t("live_5h")} <b>{h(a["last5h_incl"])}</b> tok</span>'
        f'<span class="lv">{t("live_7d")} <b>{h(a["last7d_incl"])}</b> tok</span></div>'
    )

    # (2) 进度条: 优先用官方真实% (quota.py 拉的 Anthropic 响应头); 无网/无令牌时退回本地估算
    have_official = bool(lim and lim.get("util5h") is not None)
    rows = []
    specs = (
        (t("win_5h"), lim and lim.get("util5h"), lim and lim.get("reset5h"), last5h, CAP_5H, timedelta(hours=5)),
        (t("win_7d"), lim and lim.get("util7d"), lim and lim.get("reset7d"), last7d, CAP_7D, timedelta(days=7)),
    )
    for label, official, reset, val, cap, win in specs:
        if official is not None:
            pct = max(0.0, min(100.0, official))
            head = t("q_official", pct=f"{pct:g}")
        else:
            pct = min(100.0, val / cap * 100) if cap else 0
            head = t("q_estimate", pct=f"{pct:.0f}", cap=h(cap))
        color = "#3fb950" if pct < 75 else ("#d29922" if pct < 90 else "#f85149")

        extra = ""
        if reset and reset > now:
            extra += t("q_reset_in", dur=_fmt_dur(reset - now))
            elapsed = (now - (reset - win)).total_seconds()
            frac = elapsed / win.total_seconds()
            if 0.02 <= frac <= 1 and pct > 0:
                extra += t("q_pace", pct=f"{min(100.0, pct / frac):.0f}")

        rows.append(
            f'<div class="quota-row">'
            f'<div class="quota-head"><span>{label}</span>'
            f'<span class="muted">{head}{extra}</span></div>'
            f'<div class="quota-track"><div class="quota-fill" '
            f'style="width:{pct:.1f}%;background:{color}"></div></div>'
            "</div>"
        )

    # (3) 脚注: 数据来源
    notes = ['<div class="muted" style="font-size:11px;margin-top:10px">']
    if have_official:
        upd = lim.get("updated")
        upd_s = t("q_updated", t=f"{upd:%H:%M}") if upd else ""
        notes.append(t("q_note_official", upd=upd_s, min=QUOTA_TTL // 60))
    else:
        notes.append(t("q_note_estimate"))
    notes.append("</div>")

    return live + "".join(rows) + "".join(notes)


def _card(value, label) -> str:
    return f'<div class="card"><div class="card-v">{value}</div><div class="card-l">{label}</div></div>'


def build_html(force_quota=False) -> str:
    _refresh_quota(force_quota)
    a = aggregate()
    now = datetime.now().astimezone()
    h = usage._humanize

    models = [(m, t) for m, t in sorted(a["per_model"].items(), key=lambda x: -x[1]) if t > 0]
    model_rows = "".join(
        f'<tr><td>{html.escape(m)}</td><td class="num">{h(t)}</td>'
        f'<td class="num muted">{t:,}</td></tr>'
        for m, t in models
    )

    c = a["comp"]
    comp_rows = "".join(
        f'<tr><td>{name}</td><td class="num">{h(v)}</td><td class="num muted">{v:,}</td></tr>'
        for name, v in (
            (t("comp_input"), c["input"]),
            (t("comp_output"), c["output"]),
            (t("comp_cache_read"), c["cache_read"]),
            (t("comp_cache_create"), c["cache_create"]),
        )
    )

    return f"""<!DOCTYPE html>
<html lang="{LANG}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("title")}</title>
<style>
  :root {{
    --bg:#0d1117; --panel:#161b22; --border:#30363d; --txt:#e6edf3; --muted:#8b949e;
    --accent:#ff8c5a;
    --l0:#161b22; --l1:#4a2c1a; --l2:#8a4a26; --l3:#cf6a30; --l4:#ff8c3a;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --bg:#f6f8fa; --panel:#fff; --border:#d0d7de; --txt:#1f2328; --muted:#656d76;
      --accent:#e8590c;
      --l0:#ebedf0; --l1:#ffd9b3; --l2:#ffb066; --l3:#fb8500; --l4:#cf5500;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; padding:24px; }}
  h1 {{ font-size:18px; margin:0 0 2px; }}
  .sub {{ color:var(--muted); font-size:12px; margin-bottom:20px; }}
  .muted {{ color:var(--muted); }}
  .grid {{ display:grid; gap:16px; max-width:1000px; margin:0 auto; }}
  .panel {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:18px; }}
  .panel h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin:0 0 14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
  .card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:16px; text-align:center; }}
  .card-v {{ font-size:26px; font-weight:700; color:var(--accent); }}
  .card-l {{ font-size:12px; color:var(--muted); margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; }}
  td {{ padding:6px 8px; border-bottom:1px solid var(--border); }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .quota-row {{ margin-bottom:14px; }}
  .quota-head {{ display:flex; justify-content:space-between; font-size:13px; margin-bottom:6px; }}
  .quota-track {{ height:8px; background:var(--border); border-radius:5px; overflow:hidden; }}
  .quota-fill {{ height:100%; border-radius:5px; }}
  .quota-live {{ display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center;
    font-size:12px; color:var(--muted); margin-bottom:12px;
    padding-bottom:12px; border-bottom:1px dashed var(--border); }}
  .quota-live .lv {{ background:var(--bg); border:1px solid var(--border);
    border-radius:6px; padding:3px 8px; }}
  .quota-live .lv b {{ color:var(--accent); font-variant-numeric:tabular-nums; }}
  /* 热力图 */
  .heatmap {{ overflow-x:auto; }}
  .hm-months {{ display:flex; margin-left:0; }}
  .hm-month {{ width:15px; font-size:10px; color:var(--muted); flex:0 0 15px; }}
  .hm-grid {{ display:flex; gap:3px; }}
  .hm-col {{ display:flex; flex-direction:column; gap:3px; }}
  .hm-cell {{ width:12px; height:12px; border-radius:2px; background:var(--l0); }}
  .hm-cell.lvl1 {{ background:var(--l1); }} .hm-cell.lvl2 {{ background:var(--l2); }}
  .hm-cell.lvl3 {{ background:var(--l3); }} .hm-cell.lvl4 {{ background:var(--l4); }}
  .hm-legend {{ display:flex; align-items:center; gap:3px; justify-content:flex-end;
    margin-top:8px; font-size:11px; color:var(--muted); }}
  .hm-legend .hm-cell {{ width:11px; height:11px; }}
  .hm-cap {{ font-size:11px; margin-top:6px; }}
  /* 柱状图 (小时图 / 本月图 通用) */
  .bars {{ display:flex; align-items:flex-end; gap:3px; height:150px; }}
  .bcol {{ flex:1; min-width:0; display:flex; flex-direction:column;
    justify-content:flex-end; align-items:center; height:100%; }}
  .bnum {{ font-size:8px; line-height:1.1; color:var(--muted); white-space:nowrap; margin-bottom:2px; }}
  .bbar {{ width:72%; background:var(--accent); border-radius:3px 3px 0 0; min-height:2px; }}
  .bbar.over {{ background:#f85149; }}  /* 超日预期 */
  .blbl {{ font-size:10px; color:var(--muted); margin-top:3px; height:14px; }}
</style>
</head>
<body>
<div class="grid">
  <div>
    <h1>{t("h1")}</h1>
    <div class="sub">{t("sub_main", date=f"{now:%Y-%m-%d %H:%M}", msgs=a['msg_count'], tot=h(a['total']))}</div>
  </div>

  <div class="cards">
    {_card(h(a['today']), t("card_today"))}
    {_card(h(a['week']), t("card_week"))}
    {_card(h(a['month']), t("card_month"))}
    {_card(h(a['total']), t("card_total"))}
  </div>
  <div class="sub" style="margin:-6px 0 0">{t("cards_note")}</div>

  <div class="panel">
    <h2>{t("panel_quota")}</h2>
    {build_quota(a)}
  </div>

  <div class="panel">
    <h2>{t("panel_heatmap")}</h2>
    {build_heatmap(a['per_day'])}
  </div>

  <div class="panel">
    <h2>{t("panel_monthly", ym=f"{now:%Y-%m}")}</h2>
    {build_monthly(a['per_day'], a['per_day_q'])}
  </div>

  <div class="panel">
    <h2>{t("panel_hourly")}</h2>
    {build_hourly(a['per_hour'])}
  </div>

  <div class="panel">
    <h2>{t("panel_models")}</h2>
    <table>{model_rows}</table>
  </div>

  <div class="panel">
    <h2>{t("panel_breakdown")}</h2>
    <table>{comp_rows}</table>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _serve(port: int, open_browser: bool = True):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            # 浏览器点"刷新"会带 Cache-Control: max-age=0 / Pragma: no-cache;
            # 页面自身的 60 秒自动刷新不带。手动刷新 -> 立刻拉官方最新, 否则走节流。
            hdr = (self.headers.get("Cache-Control", "") + " "
                   + self.headers.get("Pragma", "")).lower()
            force = "no-cache" in hdr or "max-age=0" in hdr
            body = build_html(force_quota=force).replace(
                "<head>", '<head>\n<meta http-equiv="refresh" content="60">', 1
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # 静默
            pass

    httpd = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"实时看板已启动: {url}  (每 60 秒自动刷新, Ctrl+C 退出)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


def main():
    global LANG
    args = sys.argv[1:]
    LANG = _detect_lang(args)
    if "--serve" in args:
        port = 8787
        if "--port" in args:
            try:
                port = int(args[args.index("--port") + 1])
            except (ValueError, IndexError):
                pass
        _serve(port, open_browser="--no-open" not in args)
        return

    out = OUT_DEFAULT
    if "-o" in args:
        try:
            out = Path(args[args.index("-o") + 1]).expanduser()
        except IndexError:
            pass
    out.write_text(build_html(), encoding="utf-8")
    print(f"已生成: {out}")
    if "--no-open" not in args:
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
