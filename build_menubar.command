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
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
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
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>LSMinimumSystemVersion</key><string>13.0</string>
    <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST

# 生成 ✨ app 图标 (访达/通知横幅上显示的就是它)。emoji 渲染失败则用系统默认图标。
# 注意末尾的 touch: 不刷新的话 Finder 会一直用缓存的旧图标。
echo "生成图标..."
osascript -l JavaScript >/dev/null 2>&1 <<'JS' || true
ObjC.import('AppKit');
var size=1024, img=$.NSImage.alloc.initWithSize($.NSMakeSize(size,size));
img.lockFocus;
var para=$.NSMutableParagraphStyle.alloc.init; para.alignment=1;
var attrs=$.NSMutableDictionary.alloc.init;
attrs.setObjectForKey($.NSFont.systemFontOfSize(800),'NSFont');
attrs.setObjectForKey(para,'NSParagraphStyle');
$.NSString.alloc.initWithUTF8String('✨').drawInRectWithAttributes($.NSMakeRect(0,-40,size,size),attrs);
img.unlockFocus;
var rep=$.NSBitmapImageRep.imageRepWithData(img.TIFFRepresentation);
rep.representationUsingTypeProperties(4,$.nil).writeToFileAtomically($('/tmp/cup-icon.png'),true);
JS

if [ -f /tmp/cup-icon.png ]; then
  ISET=/tmp/cup.iconset; rm -rf "$ISET"; mkdir -p "$ISET"
  for pair in "16 16x16" "32 16x16@2x" "32 32x32" "64 32x32@2x" \
              "128 128x128" "256 128x128@2x" "256 256x256" "512 256x256@2x" \
              "512 512x512" "1024 512x512@2x"; do
    set -- $pair
    sips -z "$1" "$1" /tmp/cup-icon.png --out "$ISET/icon_$2.png" >/dev/null
  done
  iconutil -c icns "$ISET" -o "$APP/Contents/Resources/AppIcon.icns"
  rm -rf "$ISET" /tmp/cup-icon.png
  echo "图标完成。"
else
  echo "跳过图标(emoji 渲染不可用), 用默认图标。"
fi
touch "$APP"   # 让 Finder 重新读图标(否则显示缓存的旧图标)

echo
echo "完成 → $APP"
echo "启动:  open \"$APP\"   (菜单栏右上角出现 🤖)"
echo "想开机自启: 系统设置 > 通用 > 登录项, 把这个 app 加进去。"
