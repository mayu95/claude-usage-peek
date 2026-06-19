#!/bin/bash
# 把 main.swift 编译成可双击的「Claude Usage Bar.app」(常驻 macOS 菜单栏)，无需 Xcode。
# 点菜单栏的 🤖 -> 弹窗看 5h/7d 剩余额度 -> 「展开为看板」打开完整 HTML 看板。
#
# 用法: 双击本文件, 或运行  bash build_menubar.command
# 退出常驻: 点菜单栏图标右键 -> 退出 (或 pkill -f "Claude Usage Bar")
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then echo "PATH 里找不到 python3, 请先装 Python 3。"; exit 1; fi
if ! command -v swiftc >/dev/null; then
  echo "找不到 swiftc。请先装 Xcode 命令行工具:  xcode-select --install"; exit 1
fi

APP="$HOME/Desktop/Claude Usage Bar.app"
EXEC="ClaudeUsageBar"
BUNDLE_ID="local.claude-usage-peek.menubar"
VER="$(tr -d ' \t\n\r' < "$DIR/VERSION" 2>/dev/null)"; [ -z "$VER" ] && VER="0.0.0"

echo "python3 : $PY"
echo "文件夹  : $DIR"
echo "app     : $APP"

# 选择界面语言 (默认英文; 之后也能在菜单栏右键 -> Language 里改)。
# Pick UI language (default English; also switchable later via right-click -> Language).
LANG_CHOICE="en"
if [ -t 0 ]; then
  echo
  echo "界面语言 / Language / 言語:"
  echo "  1) English (default)"
  echo "  2) 中文"
  echo "  3) 日本語"
  printf "> "
  read -r ans || true
  case "$ans" in
    2) LANG_CHOICE="zh" ;;
    3) LANG_CHOICE="ja" ;;
    *) LANG_CHOICE="en" ;;
  esac
fi
defaults write "$BUNDLE_ID" lang -string "$LANG_CHOICE" 2>/dev/null || true
echo "语言 / language : $LANG_CHOICE"

# 把本机 python 路径与项目文件夹注入编译 (不写死在源码里; 搬动文件夹后重 build 即可)
cat > Config.swift <<EOF
// 由 build_menubar.command 自动生成, 勿手改。
let kPythonPath = "$PY"
let kProjectDir = "$DIR"
let kVersion = "$VER"
EOF

echo "编译中…"
swiftc -O main.swift Config.swift -o "$EXEC"

echo "组装 .app …"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mv "$EXEC" "$APP/Contents/MacOS/$EXEC"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>Claude Usage Bar</string>
    <key>CFBundleDisplayName</key><string>Claude 用量</string>
    <key>CFBundleIdentifier</key><string>local.claude-usage-peek.menubar</string>
    <key>CFBundleVersion</key><string>$VER</string>
    <key>CFBundleShortVersionString</key><string>$VER</string>
    <key>CFBundleExecutable</key><string>$EXEC</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>LSMinimumSystemVersion</key><string>13.0</string>
    <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST

echo
echo "完成 → $APP"
echo "启动:  open \"$APP\"   (菜单栏右上角出现 🤖)"
echo "想开机自启: 系统设置 > 通用 > 登录项, 把这个 app 加进去。"
