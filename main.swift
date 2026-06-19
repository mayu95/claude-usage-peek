// claude-usage-peek menu-bar tool — native Swift, single file, built with swiftc (no Xcode).
//
// A 🤖 icon in the menu bar shows the 5h remaining quota %. Left-click opens a
// popover panel: 5h / 7d progress bars (fill = usage, green→orange→red) + remaining %
// + reset time, a "Refresh" button and an "Open dashboard →" button. Right-click
// gives a small menu (refresh / dashboard / language / quit).
//
// UI language is en / zh / ja, stored in UserDefaults key "lang" (default "en").
// It can be set at install time by build_menubar.command and switched anytime from
// the right-click menu.
//
// Data is read (read-only) from the cache quota.py writes: ~/.claude/usage-peek-quota.json
// The python path and project dir are injected by build_menubar.command into Config.swift
// (kPythonPath / kProjectDir), so no paths are hard-coded here; rebuild after moving the folder.
//
// Requires Config.swift to provide: let kPythonPath: String / let kProjectDir: String

import AppKit
import ServiceManagement

// MARK: - i18n

enum Lang: String { case en, zh, ja }

func currentLang() -> Lang {
    Lang(rawValue: UserDefaults.standard.string(forKey: "lang") ?? "en") ?? .en
}

// MARK: - 版本更新检测 / Update check

let kRepoURL = "https://github.com/mayu95/claude-usage-peek"
let kVersionURL = "https://raw.githubusercontent.com/mayu95/claude-usage-peek/main/VERSION"

/// 语义化比较: remote 是否比 local 新 (按 . 分段比数字)。
func isVersion(_ remote: String, newerThan local: String) -> Bool {
    func parts(_ s: String) -> [Int] { s.split(separator: ".").map { Int($0) ?? 0 } }
    let r = parts(remote), l = parts(local)
    for i in 0..<max(r.count, l.count) {
        let rv = i < r.count ? r[i] : 0
        let lv = i < l.count ? l[i] : 0
        if rv != lv { return rv > lv }
    }
    return false
}

let STRINGS: [String: [Lang: String]] = [
    "header":      [.en: "Claude Usage",      .zh: "Claude 用量",   .ja: "Claude 使用量"],
    "win5h":       [.en: "5-hour window",     .zh: "5 小时窗口",     .ja: "5時間ウィンドウ"],
    "win7d":       [.en: "7-day window",      .zh: "7 天窗口",       .ja: "7日間ウィンドウ"],
    // {u}=已用% {t}=重置时刻; 后面再拼 " · ≈ {p}%"(按当前速度到重置时的预计已用%)
    "line1":       [.en: "Used {u}% · reset {t}",
                    .zh: "已用 {u}% · {t} 更新",
                    .ja: "使用 {u}% · {t} リセット"],
    "nodata":      [.en: "No data yet — click Refresh", .zh: "暂无数据，点「刷新」拉取", .ja: "データなし —「更新」を押してください"],
    "noquota":     [.en: "No official quota yet (sign in to Claude Code first)",
                    .zh: "还没拿到官方限额（需登录过 Claude Code）",
                    .ja: "公式の利用上限を取得できません（Claude Code へのログインが必要）"],
    "updated":     [.en: "Updated",           .zh: "更新于",        .ja: "更新"],
    "status":      [.en: "Status",            .zh: "状态",          .ja: "ステータス"],
    "refresh":     [.en: "🔄 Refresh",         .zh: "🔄 刷新",       .ja: "🔄 更新"],
    "dashboard":   [.en: "📊 Open dashboard →", .zh: "📊 展开为看板 →", .ja: "📊 ダッシュボードを開く →"],
    "menuRefresh": [.en: "🔄 Refresh quota",   .zh: "🔄 刷新限额",   .ja: "🔄 利用上限を更新"],
    "menuDash":    [.en: "📊 Open dashboard",  .zh: "📊 展开为看板", .ja: "📊 ダッシュボードを開く"],
    "menuLang":    [.en: "Language",           .zh: "语言",          .ja: "言語"],
    "login":       [.en: "Start at login",      .zh: "开机自启",      .ja: "ログイン時に起動"],
    "quit":        [.en: "Quit",               .zh: "退出",          .ja: "終了"],
    "update_menu": [.en: "🔔 Update to {v} →",   .zh: "🔔 更新到 {v} →", .ja: "🔔 {v} に更新 →"],
    "update_title": [.en: "Claude Usage Bar — update available",
                     .zh: "Claude 用量 — 有新版本",
                     .ja: "Claude 使用量 — アップデートあり"],
    "update_body": [.en: "Version {v} is available. Open the menu → Update.",
                    .zh: "新版本 {v} 已发布，点菜单栏图标 → 更新。",
                    .ja: "バージョン {v} が公開。メニュー → 更新。"],
    "update_toggle": [.en: "Check for updates", .zh: "检查更新", .ja: "アップデートを確認"],
    "update_ask_title": [.en: "Check for updates automatically?",
                         .zh: "自动检查更新？",
                         .ja: "自動でアップデートを確認しますか？"],
    "update_ask_body": [.en: "When on, the app checks GitHub for a newer version — just a small version-number request, no data about you is sent. Off by default; you can change it anytime from the menu.",
                        .zh: "开启后，会去 GitHub 查一下有没有新版本——只发一个版本号请求、不发送你的任何数据。默认关闭，随时可在菜单里改。",
                        .ja: "オンにすると GitHub で新しいバージョンを確認します（バージョン番号の小さなリクエストのみ・あなたのデータは送信しません）。既定はオフで、メニューからいつでも変更できます。"],
    "enable":      [.en: "Enable", .zh: "开启", .ja: "オンにする"],
    "not_now":     [.en: "Not now", .zh: "暂不", .ja: "今はしない"],
    "note":        [.en: "Official rate-limit value (whole-% precision); may differ ~1% from the usage page.",
                    .zh: "官方限流值（整数精度），可能与官网用量页差约 1%。",
                    .ja: "公式のレート制限値（整数精度）。使用状況ページと約 1% 異なる場合があります。"],
]

func tr(_ key: String) -> String {
    let l = currentLang()
    return STRINGS[key]?[l] ?? STRINGS[key]?[.en] ?? key
}

// MARK: - 额度数据 / Quota data

/// 解析 ~/.claude/usage-peek-quota.json
struct Quota {
    var util5h: Double?      // 已用百分比 0~100 / used percentage
    var util7d: Double?
    var reset5h: Int?        // epoch 秒 / epoch seconds
    var reset7d: Int?
    var status: String?
    var updatedAt: String?

    static let cacheURL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".claude/usage-peek-quota.json")

    static func load() -> Quota? {
        guard let data = try? Data(contentsOf: cacheURL),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }
        let u = obj["usageData"] as? [String: Any] ?? [:]
        func d(_ k: String) -> Double? { (u[k] as? NSNumber)?.doubleValue }
        func i(_ k: String) -> Int? { (u[k] as? NSNumber)?.intValue }
        return Quota(
            util5h: d("utilization5h"), util7d: d("utilization7d"),
            reset5h: i("reset5hAt"), reset7d: i("reset7dAt"),
            status: u["limitStatus"] as? String,
            updatedAt: obj["updatedAt"] as? String
        )
    }

}

/// epoch 秒 -> "HH:mm"（今天）或 "MM-dd HH:mm"（跨天） / today vs cross-day
func fmtReset(_ ts: Int?) -> String {
    guard let ts, ts > 0 else { return "?" }
    let date = Date(timeIntervalSince1970: TimeInterval(ts))
    let cal = Calendar.current
    let f = DateFormatter()
    f.dateFormat = cal.isDateInToday(date) ? "HH:mm" : "MM-dd HH:mm"
    return f.string(from: date)
}

/// 用量百分比 -> 进度条颜色（越满越红） / bar color, redder as it fills
func barColor(_ used: Double?) -> NSColor {
    guard let used else { return .systemGray }
    switch used {
    case ..<60: return .systemGreen
    case ..<85: return .systemOrange
    default: return .systemRed
    }
}

let WINDOW_5H: Double = 5 * 3600        // 5 小时窗口长度（秒）
let WINDOW_7D: Double = 7 * 24 * 3600   // 7 天窗口长度（秒）

/// 按窗口内"已过时间"把当前已用% 线性外推到重置时刻 -> 预计已用%。
/// linear projection: at the current pace, how much of the window will be used by reset.
/// 窗口刚开始(已过时间太短)或已过重置点时不外推, 返回 nil。
func projectedAtReset(used: Double?, reset: Int?, window: Double) -> Int? {
    guard let used, let reset, reset > 0 else { return nil }
    let remaining = Double(reset) - Date().timeIntervalSince1970
    let elapsed = window - remaining
    guard remaining > 0, elapsed > 60 else { return nil }
    return min(100, max(0, Int((used * window / elapsed).rounded())))
}

// MARK: - 进度条 / Progress bar

final class BarView: NSView {
    var progress: CGFloat = 0 { didSet { needsDisplay = true } }
    var color: NSColor = .systemGreen { didSet { needsDisplay = true } }

    override func draw(_ dirtyRect: NSRect) {
        let r = bounds.height / 2
        // 轨道底色（淡） / track fill (faint)
        NSColor.separatorColor.withAlphaComponent(0.35).setFill()
        NSBezierPath(roundedRect: bounds, xRadius: r, yRadius: r).fill()
        // 已用部分 / used portion
        let w = max(bounds.height, bounds.width * min(max(progress, 0), 1))
        color.setFill()
        NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: w, height: bounds.height),
                     xRadius: r, yRadius: r).fill()
        // 轨道描边：稍深一点点, 跟随系统配色, 让进度条从背景里分出来。
        // track outline: a touch darker, theme-aware, so the bar stands out from the background.
        let inset = bounds.insetBy(dx: 0.625, dy: 0.625)
        let ri = inset.height / 2
        let border = NSBezierPath(roundedRect: inset, xRadius: ri, yRadius: ri)
        border.lineWidth = 1.25
        NSColor.tertiaryLabelColor.withAlphaComponent(0.6).setStroke()
        border.stroke()
    }
}

// MARK: - 弹窗面板 / Popover panel

final class PanelViewController: NSViewController {
    var refreshAction: (() -> Void)?
    var dashboardAction: (() -> Void)?

    private let header = NSTextField(labelWithString: "")
    private let title5h = NSTextField(labelWithString: "")
    private let bar5h = BarView()
    private let detail5h = NSTextField(labelWithString: "")
    private let title7d = NSTextField(labelWithString: "")
    private let bar7d = BarView()
    private let detail7d = NSTextField(labelWithString: "")
    private let footer = NSTextField(labelWithString: "")
    private let note = NSTextField(labelWithString: "")
    private let refreshButton = NSButton(title: "", target: nil, action: nil)
    private let dashButton = NSButton(title: "", target: nil, action: nil)

    override func loadView() {
        let container = NSView(frame: NSRect(x: 0, y: 0, width: 300, height: 310))

        header.font = .boldSystemFont(ofSize: 16)
        header.alignment = .center

        for t in [title5h, title7d] { t.font = .boldSystemFont(ofSize: 13) }
        for d in [detail5h, detail7d] {
            d.font = .systemFont(ofSize: 12)
            d.textColor = .secondaryLabelColor
        }
        footer.font = .systemFont(ofSize: 11)
        footer.textColor = .tertiaryLabelColor
        footer.alignment = .center

        note.font = .systemFont(ofSize: 10)
        note.textColor = .tertiaryLabelColor
        note.alignment = .center
        note.maximumNumberOfLines = 0
        note.lineBreakMode = .byWordWrapping

        for b in [bar5h, bar7d] {
            b.translatesAutoresizingMaskIntoConstraints = false
            b.heightAnchor.constraint(equalToConstant: 12).isActive = true
        }

        for (btn, sel) in [(refreshButton, #selector(refreshTapped)), (dashButton, #selector(dashTapped))] {
            btn.bezelStyle = .rounded
            btn.target = self
            btn.action = sel
        }

        func section(_ title: NSView, _ bar: NSView, _ detail: NSView) -> NSStackView {
            let s = NSStackView(views: [title, bar, detail])
            s.orientation = .vertical
            s.alignment = .leading
            s.spacing = 4
            return s
        }

        let stack = NSStackView(views: [
            header,
            section(title5h, bar5h, detail5h),
            section(title7d, bar7d, detail7d),
            footer,
            refreshButton,
            dashButton,
            note,
        ])
        stack.orientation = .vertical
        stack.alignment = .centerX
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 20),
            stack.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -20),
            stack.topAnchor.constraint(equalTo: container.topAnchor, constant: 18),
            stack.bottomAnchor.constraint(equalTo: container.bottomAnchor, constant: -18),
        ])
        for v in [bar5h, bar7d, refreshButton, dashButton, note] {
            v.widthAnchor.constraint(equalToConstant: 260).isActive = true
        }
        self.view = container
        applyTexts()
        refresh()
    }

    @objc private func refreshTapped() { refreshAction?() }
    @objc private func dashTapped() { dashboardAction?() }

    /// 切换语言后更新所有静态文案 / update static labels after a language switch
    func applyTexts() {
        header.stringValue = "🤖 " + tr("header")
        title5h.stringValue = tr("win5h")
        title7d.stringValue = tr("win7d")
        refreshButton.title = tr("refresh")
        dashButton.title = tr("dashboard")
        note.stringValue = tr("note")
    }

    func refresh() {
        guard let q = Quota.load() else {
            detail5h.stringValue = tr("nodata")
            detail7d.stringValue = ""
            bar5h.progress = 0; bar7d.progress = 0
            footer.stringValue = tr("noquota")
            return
        }
        // 第一行: 已用% + 预计更新时间; 第二行: 按当前速度到重置时的预计已用%
        func detailText(_ used: Double?, _ reset: Int?, _ window: Double) -> String {
            let u = used == nil ? "?" : String(format: "%.0f", used!)
            var s = tr("line1").replacingOccurrences(of: "{u}", with: u)
                               .replacingOccurrences(of: "{t}", with: fmtReset(reset))
            if let p = projectedAtReset(used: used, reset: reset, window: window) {
                s += " · ≈ \(p)%"
            }
            return s
        }
        bar5h.progress = CGFloat((q.util5h ?? 0) / 100); bar5h.color = barColor(q.util5h)
        bar7d.progress = CGFloat((q.util7d ?? 0) / 100); bar7d.color = barColor(q.util7d)
        detail5h.stringValue = detailText(q.util5h, q.reset5h, WINDOW_5H)
        detail7d.stringValue = detailText(q.util7d, q.reset7d, WINDOW_7D)

        var foot = ""
        if let upd = q.updatedAt, let date = ISO8601DateFormatter().date(from: upd) {
            let f = DateFormatter(); f.dateFormat = "HH:mm"
            foot = "\(tr("updated")) \(f.string(from: date))"
        }
        if let s = q.status, s != "allowed" { foot += (foot.isEmpty ? "" : " · ") + "\(tr("status")) \(s)" }
        footer.stringValue = foot
    }
}

// MARK: - 主控制器 / App controller

final class AppController: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private let popover = NSPopover()
    private var panel: PanelViewController!
    private let port = "8787"
    private var newerVersion: String?   // 远端更新的版本号(仅当比本地新时置位)

    func applicationDidFinishLaunching(_ n: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "🤖 …"
        statusItem.button?.target = self
        statusItem.button?.action = #selector(statusClicked)
        statusItem.button?.sendAction(on: [.leftMouseUp, .rightMouseUp])

        panel = PanelViewController()
        panel.refreshAction = { [weak self] in self?.refreshQuota() }
        panel.dashboardAction = { [weak self] in self?.openDashboard() }
        popover.contentViewController = panel
        popover.behavior = .transient

        updateTitle()
        refreshQuota()  // 启动先拉一次 / fetch once on launch

        // 每 120 秒后台刷新限额 + 更新菜单栏标题。额度变化慢, 不必更勤(每次都打一次 API)。
        // refresh every 120s — quota changes slowly, no need to poll the API more often.
        let t = Timer.scheduledTimer(withTimeInterval: 120, repeats: true) { [weak self] _ in
            self?.refreshQuota()
        }
        RunLoop.main.add(t, forMode: .common)

        // 更新检测默认关闭(隐私优先)。首次启动弹一次询问; 开启后才检查, 之后每 6 小时一次。
        if UserDefaults.standard.object(forKey: "updateCheck") == nil {
            DispatchQueue.main.async { [weak self] in self?.promptUpdateOptIn() }
        } else {
            checkForUpdate()
        }
        let ut = Timer.scheduledTimer(withTimeInterval: 6 * 3600, repeats: true) { [weak self] _ in
            self?.checkForUpdate()
        }
        RunLoop.main.add(ut, forMode: .common)
    }

    /// 首次启动弹窗询问是否开启自动检查更新(默认不开)。记住选择, 不再弹。
    private func promptUpdateOptIn() {
        let a = NSAlert()
        a.messageText = tr("update_ask_title")
        a.informativeText = tr("update_ask_body")
        a.addButton(withTitle: tr("enable"))
        a.addButton(withTitle: tr("not_now"))
        NSApp.activate(ignoringOtherApps: true)
        let on = (a.runModal() == .alertFirstButtonReturn)
        UserDefaults.standard.set(on, forKey: "updateCheck")
        if on { checkForUpdate() }
    }

    /// 拉 GitHub 上的 VERSION 比对本地版本; 有新版则记下并提醒(仅首次)。
    /// 只 GET 一个版本号小文件, 不发送任何数据; 离线/出错就静默跳过。
    private func checkForUpdate() {
        guard UserDefaults.standard.bool(forKey: "updateCheck") else { return }   // 未开启则不检查
        guard let url = URL(string: kVersionURL) else { return }
        var req = URLRequest(url: url)
        req.timeoutInterval = 10
        req.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: req) { [weak self] data, _, _ in
            guard let self, let data,
                  let raw = String(data: data, encoding: .utf8) else { return }
            let remote = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !remote.isEmpty, remote.allSatisfy({ $0.isNumber || $0 == "." }),
                  isVersion(remote, newerThan: kVersion) else { return }
            DispatchQueue.main.async {
                let firstTime = (self.newerVersion != remote)
                self.newerVersion = remote
                self.updateTitle()
                if firstTime { self.notifyUpdate(remote) }
            }
        }.resume()
    }

    /// 弹一条 macOS 通知(用 osascript, 与项目其它部分一致, 无需额外权限)。
    private func notifyUpdate(_ v: String) {
        let title = tr("update_title")
        let body = tr("update_body").replacingOccurrences(of: "{v}", with: v)
        run(["/usr/bin/osascript", "-e",
             "display notification \"\(body)\" with title \"\(title)\""], wait: false)
    }

    /// 用缓存刷新菜单栏标题（显示 5h 剩余%） / menu-bar title shows 5h remaining %
    private func updateTitle() {
        let q = Quota.load()
        let dot = newerVersion != nil ? " •" : ""   // 有更新时加个小圆点
        if let used = q?.util5h {
            statusItem.button?.title = "🤖 \(max(0, 100 - Int(used.rounded())))%\(dot)"
        } else {
            statusItem.button?.title = "🤖 ?\(dot)"
        }
        if popover.isShown { panel.refresh() }
    }

    /// 后台跑 quota.py --quiet 刷新缓存，完成后回主线程更新 UI
    private func refreshQuota() {
        DispatchQueue.global(qos: .utility).async { [weak self] in
            self?.run([kPythonPath, "\(kProjectDir)/quota.py", "--quiet"], wait: true)
            DispatchQueue.main.async { self?.updateTitle() }
        }
    }

    /// 启动本地看板服务（已在跑会先杀掉用最新代码重起）并打开浏览器
    private func openDashboard() {
        let cmd = """
        pkill -f "dashboard.py --serve --port \(port)" 2>/dev/null; \
        sleep 0.6; \
        nohup "\(kPythonPath)" "\(kProjectDir)/dashboard.py" --serve --port \(port) --no-open --lang \(currentLang().rawValue) \
          >> "$HOME/.claude-usage-dash.log" 2>&1 & \
        sleep 1.5; \
        open "http://127.0.0.1:\(port)"
        """
        run(["/bin/zsh", "-c", cmd], wait: false)
        popover.performClose(nil)
    }

    private func run(_ args: [String], wait: Bool) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: args[0])
        p.arguments = Array(args.dropFirst())
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do {
            try p.run()
            if wait { p.waitUntilExit() }
        } catch { /* 忽略：python 缺失等 / ignore: python missing, etc. */ }
    }

    @objc private func statusClicked() {
        if NSApp.currentEvent?.type == .rightMouseUp {
            showContextMenu()
        } else {
            togglePopover()
        }
    }

    private func togglePopover() {
        guard let button = statusItem.button else { return }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            panel.refresh()
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        }
    }

    private func showContextMenu() {
        let menu = NSMenu()
        // 有新版时, 置顶一条"更新"项
        if let v = newerVersion {
            let up = NSMenuItem(title: tr("update_menu").replacingOccurrences(of: "{v}", with: v),
                                action: #selector(openRepo), keyEquivalent: "")
            up.target = self
            menu.addItem(up)
            menu.addItem(.separator())
        }
        menu.addItem(withTitle: tr("menuRefresh"), action: #selector(menuRefresh), keyEquivalent: "r").target = self
        menu.addItem(withTitle: tr("menuDash"), action: #selector(menuDash), keyEquivalent: "d").target = self
        menu.addItem(.separator())

        // 语言子菜单 / language submenu
        let langItem = NSMenuItem(title: tr("menuLang"), action: nil, keyEquivalent: "")
        let langMenu = NSMenu()
        for (code, name) in [("en", "English"), ("zh", "中文"), ("ja", "日本語")] {
            let it = NSMenuItem(title: name, action: #selector(pickLang(_:)), keyEquivalent: "")
            it.target = self
            it.representedObject = code
            it.state = (code == currentLang().rawValue) ? .on : .off
            langMenu.addItem(it)
        }
        menu.addItem(langItem)
        menu.setSubmenu(langMenu, for: langItem)

        // 开机自启开关（系统 SMAppService, macOS 13+）
        let loginItem = NSMenuItem(title: tr("login"), action: #selector(toggleLogin), keyEquivalent: "")
        loginItem.target = self
        loginItem.state = (SMAppService.mainApp.status == .enabled) ? .on : .off
        menu.addItem(loginItem)

        let updItem = NSMenuItem(title: tr("update_toggle"), action: #selector(toggleUpdateCheck), keyEquivalent: "")
        updItem.target = self
        updItem.state = UserDefaults.standard.bool(forKey: "updateCheck") ? .on : .off
        menu.addItem(updItem)

        menu.addItem(.separator())
        menu.addItem(withTitle: tr("quit"), action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        if let button = statusItem.button {
            menu.popUp(positioning: nil, at: NSPoint(x: 0, y: button.bounds.height + 4), in: button)
        }
    }

    @objc private func menuRefresh() { refreshQuota() }
    @objc private func menuDash() { openDashboard() }
    @objc private func openRepo() {
        if let url = URL(string: kRepoURL) { NSWorkspace.shared.open(url) }
    }

    /// 开关自动检查更新。开 -> 立刻查一次; 关 -> 清掉更新提示。
    @objc private func toggleUpdateCheck() {
        let on = !UserDefaults.standard.bool(forKey: "updateCheck")
        UserDefaults.standard.set(on, forKey: "updateCheck")
        if on {
            checkForUpdate()
        } else {
            newerVersion = nil
            updateTitle()
        }
    }

    /// 切换"开机自启"。失败(例如需在系统设置里批准)则忽略, 下次打开菜单会反映真实状态。
    @objc private func toggleLogin() {
        do {
            if SMAppService.mainApp.status == .enabled {
                try SMAppService.mainApp.unregister()
            } else {
                try SMAppService.mainApp.register()
            }
        } catch {
            NSLog("login item toggle failed: \(error)")
        }
    }

    @objc private func pickLang(_ sender: NSMenuItem) {
        guard let code = sender.representedObject as? String else { return }
        UserDefaults.standard.set(code, forKey: "lang")
        panel.applyTexts()
        panel.refresh()
        updateTitle()
    }
}

// MARK: - 启动 / Launch

let app = NSApplication.shared
app.setActivationPolicy(.accessory)   // 不进 Dock，只在菜单栏 / menu bar only, no Dock
let controller = AppController()
app.delegate = controller
app.run()
