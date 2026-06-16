# claude-usage-peek（中文版）

> English version (separate repo): **https://github.com/mayu95/claude-usage-peek-en**

轻量、**纯本地**、安全的 Claude Code 用量查看工具。零依赖（只用 Python 3 标准库），
读 `~/.claude/projects/**/*.jsonl` 里每条 assistant 消息的 token 用量。

> **🔒 纯本地 · 很安全**：所有统计/分析都在你本机完成，**用量数据绝不上传、不外发、不经任何第三方**，
> 也不修改 Claude 的数据。默认离线即可用；唯一的网络访问是**可选的** `quota.py`——它只向
> **官方 api.anthropic.com** 用你自己的登录令牌**读取**限额%（只读、不发送任何数据、令牌不落盘）。
> 不想联网就别用它，看板照常工作（显示本地估算）。

> **🛠 本项目完全用 [Claude Code](https://claude.com/claude-code)（cc）开发。**

## 三步开始

本工具零依赖、不用 `pip install`——只需电脑里有 **Python 3**（没有就先装一个 Python 3）。无需账号、无需配置。

1. **下载本文件夹**,打开**「终端」**应用,进入该文件夹:
   ```bash
   cd 你的路径/claude-usage-peek
   ```
   (小技巧:先敲 `cd ` 加一个空格,再把文件夹拖到终端窗口里。)
2. **查看用量** —— 运行:
   ```bash
   python3 dashboard.py
   ```
   浏览器会打开一个看板,用图表展示你用了多少。
3. **(macOS,可选)做个桌面图标**,以后不用再开终端:
   ```bash
   bash make_app.command
   ```
   桌面出现 🤖 **Claude Usage** 图标,以后双击它就行。

大多数人到这就够了,下面是细节和选项。

## 适用范围(统计谁的用量)

- **图表(今日/热力图/小时/月度)= 本机的 *Claude Code* 用量**:凡是会往
  `~/.claude/projects/` 写会话的入口都算——终端 CLI(`claude`)、**VS Code** 扩展、
  其它 IDE 扩展(JetBrains 等)。**不含 claude.ai 网页版、也不含 Claude 桌面聊天 app**
  (它们不是 Claude Code,不写这里)。
- **官方 5h / 7d 限额%**(`quota.py`)= **整个账号**的限额,涵盖你账号下的所有用量
  (网页、桌面、Claude Code、API),因为这是 Anthropic 的统一限额。

一句话:**图表是本机 Claude Code 的量,百分比是整个账号的量。**

## 平台支持

- **macOS — 完整支持**(文本、看板、官方额度、通知、桌面图标)。
- **Linux** — `usage.py` / `dashboard.py` / `quota.py` 可用(Linux 上令牌从
  `~/.claude/.credentials.json` 读,因为没有 macOS 钥匙串);通知 `watch.py` 和
  `make_app.command` **仅 macOS**。
- **Windows — 不支持**(取令牌、通知、图标都依赖 macOS 工具;需要的话用 WSL)。

## 它统计什么

每条消息的 token = `input + cache_creation + cache_read + output`（含 cache）。
用 `message.id` 去重，避免重试/重放被重复计数。**只看 token 数，不折算花费。**

## 两种用法

### 1) 命令行查明细

```bash
python3 usage.py        # 按天 + 按模型汇总
python3 usage.py --json  # 机器可读的 JSON
```

输出示例：

```
Claude Code 本地用量 (token, 含 cache)
========================================
总计: 37.1M tok  (37,107,427)  · 552 条消息

按天 (最近 14 天):
  2026-06-16   488.6k  █
  2026-06-11    16.9M  ██████████████████
  ...

按模型:
  claude-opus-4-8            31.4M  (31,419,889)
  claude-haiku-4-5-20251001    5.7M  (5,687,538)
```

### 2) VS Code 里的 Claude Code 状态栏 (statusline)

把下面这段加入 `~/.claude/settings.json`（命令需用**绝对路径**，把路径换成你本机的仓库位置）：

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/claude-usage-peek/usage.py"
  }
}
```

Claude Code 会通过 stdin 把当前会话信息传给脚本，状态栏即显示一行：

```
⊙ Opus 4.8 · 本会话 1.2M · 今日 1.7M · 本周 1.7M · 本月 38.3M tok · 5h 余 86% · 7d 余 96%
```

- `⊙ 模型 / 本会话 / 今日·本周·本月`：模型、当前对话、各时段累计 token
- `5h / 7d 余`：限额窗口剩余%，读自 `quota.py` 写的本地缓存（没拉取过则不显示）

> 注意：statusLine 只在终端 CLI 渲染，**VS Code 扩展面板不显示**；面板用户请用看板或桌面图标。

> statusline 配置**不会热加载**，改完必须**关掉当前会话、重开一个新会话**才会显示。

### 3) HTML 看板 (热力图)

`statusLine` 只在终端 CLI 渲染，**VS Code 扩展面板不显示**。要图形化看板就用这个：

```bash
python3 dashboard.py        # 生成并自动打开
python3 dashboard.py --no-open  # 只生成 dashboard.html
python3 dashboard.py --serve    # 本地实时看板, 每60秒自刷新
```

看板内容：今日/本周/本月/累计 token 卡片、官方 5h/7d 限额进度条（带重置倒计时）、
**GitHub 式每日用量热力图（自首次使用起，对数色阶）**、
按小时分布柱状图、**本月每日用量柱状图（超日预期标红、柱顶标数字）**、按模型、token 分项。

- 纯 HTML + CSS，**无 JavaScript、无 CDN**，自包含单文件。
- 配色跟随系统深色/浅色。
- `--serve` 模式只监听 `127.0.0.1`，仅本机可访问。

### 4) 后台看门狗 (到 50%/75%/90% 弹通知)

常驻后台, 用量到 50%/75%/90% 时各弹一次 macOS 通知(优先官方%, 取不到退回估算)。
每次检查约 0.1 秒, CPU 可忽略。

```bash
python3 watch.py                 # 默认三级 50/75/90
python3 watch.py --levels 60,85  # 自定义级别
nohup python3 watch.py >> ~/.claude-usage-watch.log 2>&1 &  # 后台常驻
pkill -f claude-usage-peek/watch.py   # 停止
python3 watch.py --once --levels 5  # 测试弹窗
```

首次需在「系统设置 → 通知」给终端开通知权限。

### 调整刷新间隔 / 提醒级别

- **看板官方%刷新间隔**: `dashboard.py` 顶部 `QUOTA_TTL`(秒, 默认 300 = 5 分钟)。
- **提醒级别**: `watch.py --levels 50,75,90`(默认), 或单级 `--threshold 80`。

### 5) 官方实时额度 quota.py

```bash
python3 quota.py   # 打印官方 5h/7d% (连一次 api.anthropic.com)
```

### 6) 桌面图标 (macOS)

```bash
bash make_app.command   # 或在访达里双击该文件
```

在桌面生成一个可双击的 **🤖 Claude Usage.app**:点一下就启动本地服务并打开看板,
不弹终端。用本机 python 路径和本文件夹,移动文件夹后重跑一次即可。可拖进 Dock 常驻。

## 卸载

一键清干净(仅 macOS,在仓库目录里运行):

```bash
bash uninstall.command   # 或在访达里双击该文件
```

它会:停掉后台服务/看门狗、删除桌面图标、删除缓存与日志、移除 `~/.claude/settings.json`
里指向本工具的 statusLine,最后询问是否连文件夹一起删。本工具从没装过任何系统级东西或依赖,所以删完即净。

## 安全说明

- 用量统计部分只读本地文件、**不联网**；唯一联网的是 `quota.py`：用你本机
  Claude Code 登录令牌只向 **api.anthropic.com**（官方）发一次请求读取真实限额%，
  **不经任何第三方**，令牌不落盘、不打印。不修改 `~/.claude/projects` 下的数据。
- 无第三方依赖，单文件可审计：[usage.py](usage.py)。
