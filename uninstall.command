#!/bin/bash
# 一键干净卸载 claude-usage-peek (仅 macOS)。
# 清掉本工具在系统里留下的一切: 后台服务、桌面图标、缓存/日志、statusLine 配置;
# 最后可选删除本文件夹。也没装过任何系统级东西/依赖。
#
# 用法: 双击本文件, 或运行  bash uninstall.command
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "正在卸载 claude-usage-peek ..."

# 1) 停掉后台服务 / 看门狗
pkill -f "claude-usage-peek.*dashboard.py" 2>/dev/null && echo "  · 已停止看板服务" || true
pkill -f "claude-usage-peek.*watch.py" 2>/dev/null && echo "  · 已停止看门狗" || true

# 2) 桌面图标
rm -rf "$HOME/Desktop/Claude Usage.app" && echo "  · 已删除桌面图标" || true

# 3) 缓存 + 日志 (只含百分比/日志, 无敏感信息)
rm -f "$HOME/.claude/usage-peek-quota.json" \
      "$HOME/.claude-usage-dash.log" \
      "$HOME/.claude-usage-watch.log" && echo "  · 已删除缓存和日志" || true

# 4) 移除 ~/.claude/settings.json 里指向本工具的 statusLine (仅当确实指向本工具)
python3 - <<'PY' 2>/dev/null || true
import json, os
p = os.path.expanduser("~/.claude/settings.json")
try:
    d = json.load(open(p))
except Exception:
    raise SystemExit
sl = d.get("statusLine")
cmd = sl.get("command", "") if isinstance(sl, dict) else ""
if "claude-usage-peek" in cmd or "usage.py" in cmd:
    d.pop("statusLine", None)
    json.dump(d, open(p, "w"), indent=2)
    print("  · 已从 ~/.claude/settings.json 移除 statusLine")
PY

# 5) 提示 shell 快捷命令 (无法安全自动改 rc, 手动删)
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ -f "$rc" ] && grep -q "claude-usage-peek" "$rc"; then
    echo "  · 注意: $rc 里有引用本工具的快捷函数(cup()/cc()), 请手动删除那一段。"
  fi
done

echo "  · 没有任何系统级安装/依赖需要清理。"
echo

# 6) 可选: 删除本文件夹
if [ -t 0 ]; then
  printf "是否连同本文件夹一起删除? %s [y/N] " "$DIR"
  read -r ans
  if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    cd "$HOME" && rm -rf "$DIR" && echo "已删除 $DIR。卸载完成 ✅"
    exit 0
  fi
fi
echo "其余已清理完毕。要删除程序本体, 运行: rm -rf \"$DIR\""
echo "卸载完成 ✅"
