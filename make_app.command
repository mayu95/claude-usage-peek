#!/bin/bash
# 在桌面生成一个可双击的「Claude Usage.app」: 点开就启动本地看板(已在跑则跳过)
# 并打开浏览器, 带 🤖 图标。用本机的 python 路径和本文件夹, 不写死路径。
# 移动过文件夹后重新跑一次即可。仅 macOS。
#
# 用法: 双击本文件, 或运行  bash make_app.command
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || true)"
APP="$HOME/Desktop/Claude Usage.app"

if [ -z "$PY" ]; then
  echo "PATH 里找不到 python3, 请先装 Python 3。"; exit 1
fi
echo "python3 : $PY"
echo "文件夹  : $DIR"
echo "app     : $APP"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Claude Usage</string>
  <key>CFBundleDisplayName</key><string>Claude Usage</string>
  <key>CFBundleIdentifier</key><string>local.claude-usage-peek</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleExecutable</key><string>run</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST

# 启动脚本: 每次点击都重启服务(用最新代码/上限), 再开浏览器
cat > "$APP/Contents/MacOS/run" <<RUN
#!/bin/bash
PY="$PY"
DIR="$DIR"
PORT=8787
/usr/bin/pkill -f "dashboard.py --serve --port \$PORT" 2>/dev/null
/bin/sleep 0.6
/usr/bin/nohup "\$PY" "\$DIR/dashboard.py" --serve --port "\$PORT" --no-open \\
  >> "\$HOME/.claude-usage-dash.log" 2>&1 &
/bin/sleep 1.5
/usr/bin/open "http://127.0.0.1:\$PORT"
RUN
chmod +x "$APP/Contents/MacOS/run"

echo "生成图标..."
osascript -l JavaScript >/dev/null 2>&1 <<'JS' || true
ObjC.import('AppKit');
var size=1024, img=$.NSImage.alloc.initWithSize($.NSMakeSize(size,size));
img.lockFocus;
var para=$.NSMutableParagraphStyle.alloc.init; para.alignment=1;
var attrs=$.NSMutableDictionary.alloc.init;
attrs.setObjectForKey($.NSFont.systemFontOfSize(800),'NSFont');
attrs.setObjectForKey(para,'NSParagraphStyle');
$.NSString.alloc.initWithUTF8String('🤖').drawInRectWithAttributes($.NSMakeRect(0,-40,size,size),attrs);
img.unlockFocus;
var rep=$.NSBitmapImageRep.imageRepWithData(img.TIFFRepresentation);
rep.representationUsingTypeProperties(4,$.nil).writeToFileAtomically($('/tmp/cup-robot.png'),true);
JS

if [ -f /tmp/cup-robot.png ]; then
  ISET=/tmp/cup.iconset; rm -rf "$ISET"; mkdir -p "$ISET"
  for pair in "16 16x16" "32 16x16@2x" "32 32x32" "64 32x32@2x" \
              "128 128x128" "256 128x128@2x" "256 256x256" "512 256x256@2x" \
              "512 512x512" "1024 512x512@2x"; do
    set -- $pair
    sips -z "$1" "$1" /tmp/cup-robot.png --out "$ISET/icon_$2.png" >/dev/null
  done
  iconutil -c icns "$ISET" -o "$APP/Contents/Resources/AppIcon.icns"
  rm -rf "$ISET" /tmp/cup-robot.png
  echo "图标完成。"
else
  echo "跳过图标(emoji 渲染不可用), 用默认图标。"
fi

touch "$APP"
killall Finder 2>/dev/null || true
killall Dock 2>/dev/null || true

echo
echo "完成。桌面上的 '$APP' 双击即可打开看板。"
echo "想常驻可把它拖进 Dock。"
