# claude-usage-peek

[English](README.md) · **中文** · [日本語](README.ja.md)

> 本项目完全用 [Claude Code](https://claude.com/claude-code) 开发。

一个 macOS 菜单栏小工具，随时看一眼你的 Claude 用量。

- **不获取你的任何信息** —— 不追踪、不做分析；你的任何信息都不会离开这台 Mac。
- **轻量** —— 就一个小小的菜单栏图标；无需 `pip install`，后台不做重活。
- **安全** —— 只读，绝不改动你的 Claude 数据。

菜单栏里有个 🤖 图标，显示你 5 小时窗口还剩多少额度。点一下弹出小面板，看 5h / 7d
限额和重置时间；也能展开成带图表和热力图的完整 HTML 看板。

> **🔒 纯本地 · 很安全**：所有统计都在你本机完成，**用量数据绝不上传、不外发、不经任何第三方**，
> 也不修改 Claude 的任何数据。唯一的网络访问是向**官方 `api.anthropic.com`** 用你自己的
> 登录令牌**读取一次**真实限额%（只读、不发送任何数据、令牌不落盘、不打印）。

## 环境要求

- **macOS 13+**
- **Python 3** —— 读用量和限额的引擎（`python3` 在 PATH 里即可）
- **Xcode 命令行工具**（需要 `swiftc` 来编译一次 app）——
  用 `xcode-select --install` 安装

> 不用 `pip install`、无第三方包、无需账号、无需配置。

## 安装

1. **下载本文件夹**（clone 或下载 ZIP）。
2. **编译 app** —— 在访达里双击 `build_menubar.command`，或在终端运行：
   ```bash
   bash build_menubar.command
   ```
   它会问你**界面语言**（English / 中文 / 日本語，默认英文，之后随时能改），
   编译后在桌面生成 **Claude Usage Bar.app**。
3. **打开 app** —— 双击 `Claude Usage Bar.app`，菜单栏右上角出现 🤖。

> 移动过文件夹？重新跑一次 `build_menubar.command` 即可。
>
> 想开机自启：右键点 🤖 → **开机自启**（打勾切换）。也可手动在**系统设置 → 通用 → 登录项**里添加。

## 使用

- **左键点** 🤖 → 弹出面板：
  - **5 小时窗口** 和 **7 天窗口** 进度条（填充=已用，绿→橙→红）、**已用%**、**预计更新时间**，
    以及**按当前速度到重置时的预计已用%**
  - **🔄 刷新** —— 重新拉官方限额
  - **📊 展开为看板 →** —— 用浏览器打开完整 HTML 看板
- **右键点** 🤖 → 小菜单：**刷新限额** / **展开为看板** /
  **语言（Language）** / **退出**。

### 怎么改语言

安装时会选一次语言（默认英文）。之后想改：**右键点菜单栏的 🤖 图标 → 语言（Language）**，
再选 **English / 中文 / 日本語**。立即生效，下次打开也会记住，不用重新编译。展开的 HTML 看板也会用所选语言。

## 这些数字是什么

- **5h / 7d %** = 你**整个 Anthropic 账号**的官方限额（网页、桌面、Claude Code、API
  —— 这是 Anthropic 的统一限额），从官方 API 读取。
- **看板里的图表** = 你**本机 *Claude Code* 的用量**（终端 CLI、VS Code 及其它 IDE 扩展
  —— 凡是会往 `~/.claude/projects/` 写会话的入口）。**不含 claude.ai 网页版，也不含
  Claude 桌面聊天 app。**

看板是一个自包含的 HTML 页面（无 JavaScript、无 CDN）：今日 / 本周 / 本月 / 累计 token
卡片、官方 5h/7d 限额条（带重置倒计时）、GitHub 式每日热力图、按小时柱状图、按模型分项。
它的本地服务只监听 `127.0.0.1`，仅本机可访问。

## 卸载

```bash
bash uninstall.command   # 或在访达里双击
```

它会退出菜单栏程序和后台服务，删除桌面 app、缓存、日志和语言偏好，并（可选）删除文件夹。
本工具从没装过任何系统级东西，删完即净。

## 进阶 —— 命令行工具（可选）

app 的引擎是几个可审计的小 Python 脚本，你也可以直接运行：

```bash
python3 usage.py            # 按天 + 按模型的 token 汇总（加 --json 出原始数据）
python3 dashboard.py        # 生成并打开 HTML 看板
python3 dashboard.py --serve  # 本地实时看板 http://127.0.0.1:8787
python3 quota.py            # 打印官方 5h/7d%（连一次 api.anthropic.com）
python3 watch.py            # 后台看门狗：用量到 50/75/90% 弹 macOS 通知
```

也可以把 `usage.py` 接进 Claude Code 终端的 **statusline** —— 见 [usage.py](usage.py)。
（statusline 只在终端 CLI 渲染，VS Code 面板不显示。）

## 安全说明

- 用量统计只读本地文件、**不联网**；唯一联网的是 `quota.py`：用你本机 Claude Code
  登录令牌只向 **api.anthropic.com**（官方）发一次请求读取真实限额%，**不经任何第三方，
  令牌不落盘、不打印**。不修改 `~/.claude/projects` 下的数据。
- 菜单栏 app 只读限额缓存（`~/.claude/usage-peek-quota.json`）并调用自带的 Python 脚本，
  自身不发起任何网络请求。
- 无第三方依赖，单文件可审计：[usage.py](usage.py)、[quota.py](quota.py)。
