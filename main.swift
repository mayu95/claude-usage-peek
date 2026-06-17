// claude-usage-peek 菜单栏小工具 —— 原生 Swift，单文件，swiftc 编译，无需 Xcode。
//
// 菜单栏出现 🤖 + 5h 剩余额度%。左键点开是个弹窗面板：
//   · 5h / 7d 两条进度条（用量填充，绿→橙→红）+ 剩余% + 重置时间
//   · 「🔄 刷新」重新拉官方限额
//   · 「📊 展开为看板 →」启动本地服务并用浏览器打开完整 HTML 看板
// 右键点图标 = 小菜单（刷新 / 展开 / 退出）。
//
// 数据来自 quota.py 写的缓存 ~/.claude/usage-peek-quota.json（只读）。
// python 路径和项目文件夹由 build_menubar.command 生成的 Config.swift 注入
// （kPythonPath / kProjectDir），所以本文件不写死路径；搬动文件夹后重新 build 即可。
//
// 依赖 Config.swift 提供：let kPythonPath: String / let kProjectDir: String
// 详见 build_menubar.command。

import AppKit

// MARK: - 额度数据

/// 解析 ~/.claude/usage-peek-quota.json
struct Quota {
    var util5h: Double?      // 已用百分比 0~100
    var util7d: Double?
    var reset5h: Int?        // epoch 秒
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

    func remaining(_ used: Double?) -> Int? {
        guard let used else { return nil }
        return max(0, Int((100 - used).rounded()))
    }
}

/// epoch 秒 -> "HH:mm"（今天）或 "MM-dd HH:mm"（跨天）
func fmtReset(_ ts: Int?) -> String {
    guard let ts, ts > 0 else { return "?" }
    let date = Date(timeIntervalSince1970: TimeInterval(ts))
    let cal = Calendar.current
    let f = DateFormatter()
    f.dateFormat = cal.isDateInToday(date) ? "HH:mm" : "MM-dd HH:mm"
    return f.string(from: date)
}

/// 用量百分比 -> 进度条颜色（越满越红）
func barColor(_ used: Double?) -> NSColor {
    guard let used else { return .systemGray }
    switch used {
    case ..<60: return .systemGreen
    case ..<85: return .systemOrange
    default: return .systemRed
    }
}

// MARK: - 进度条

final class BarView: NSView {
    var progress: CGFloat = 0 { didSet { needsDisplay = true } }
    var color: NSColor = .systemGreen { didSet { needsDisplay = true } }

    override func draw(_ dirtyRect: NSRect) {
        let r = bounds.height / 2
        NSColor.separatorColor.withAlphaComponent(0.35).setFill()
        NSBezierPath(roundedRect: bounds, xRadius: r, yRadius: r).fill()
        let w = max(bounds.height, bounds.width * min(max(progress, 0), 1))
        color.setFill()
        NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: w, height: bounds.height),
                     xRadius: r, yRadius: r).fill()
    }
}

// MARK: - 弹窗面板

final class PanelViewController: NSViewController {
    var refreshAction: (() -> Void)?
    var dashboardAction: (() -> Void)?

    private let title5h = NSTextField(labelWithString: "5 小时窗口")
    private let bar5h = BarView()
    private let detail5h = NSTextField(labelWithString: "")
    private let title7d = NSTextField(labelWithString: "7 天窗口")
    private let bar7d = BarView()
    private let detail7d = NSTextField(labelWithString: "")
    private let footer = NSTextField(labelWithString: "")
    private let refreshButton = NSButton(title: "🔄 刷新", target: nil, action: nil)
    private let dashButton = NSButton(title: "📊 展开为看板 →", target: nil, action: nil)

    override func loadView() {
        let container = NSView(frame: NSRect(x: 0, y: 0, width: 300, height: 270))

        let header = NSTextField(labelWithString: "🤖 Claude 用量")
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
            stack.bottomAnchor.constraint(lessThanOrEqualTo: container.bottomAnchor, constant: -18),
        ])
        for v in [bar5h, bar7d, refreshButton, dashButton] {
            v.widthAnchor.constraint(equalToConstant: 260).isActive = true
        }
        self.view = container
        refresh()
    }

    @objc private func refreshTapped() { refreshAction?() }
    @objc private func dashTapped() { dashboardAction?() }

    func refresh() {
        guard let q = Quota.load() else {
            detail5h.stringValue = "暂无数据，点「刷新」拉取"
            detail7d.stringValue = ""
            bar5h.progress = 0; bar7d.progress = 0
            footer.stringValue = "还没拿到官方限额（需登录过 Claude Code）"
            return
        }
        func line(_ used: Double?, _ reset: Int?) -> String {
            let rem = q.remaining(used)
            let u = used == nil ? "?" : String(format: "%.0f", used!)
            return "已用 \(u)% · 剩 \(rem.map { "\($0)" } ?? "?")% · 重置 \(fmtReset(reset))"
        }
        bar5h.progress = CGFloat((q.util5h ?? 0) / 100); bar5h.color = barColor(q.util5h)
        bar7d.progress = CGFloat((q.util7d ?? 0) / 100); bar7d.color = barColor(q.util7d)
        detail5h.stringValue = line(q.util5h, q.reset5h)
        detail7d.stringValue = line(q.util7d, q.reset7d)

        var foot = ""
        if let upd = q.updatedAt, let date = ISO8601DateFormatter().date(from: upd) {
            let f = DateFormatter(); f.dateFormat = "HH:mm"
            foot = "更新于 \(f.string(from: date))"
        }
        if let s = q.status, s != "allowed" { foot += (foot.isEmpty ? "" : " · ") + "状态 \(s)" }
        footer.stringValue = foot
    }
}

// MARK: - 主控制器

final class AppController: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private let popover = NSPopover()
    private var panel: PanelViewController!
    private let port = "8787"

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
        refreshQuota()  // 启动先拉一次

        // 每 60 秒后台刷新限额 + 更新菜单栏标题
        let t = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.refreshQuota()
        }
        RunLoop.main.add(t, forMode: .common)
    }

    /// 用缓存刷新菜单栏标题（显示 5h 剩余%）
    private func updateTitle() {
        let q = Quota.load()
        if let rem = q?.remaining(q?.util5h) {
            statusItem.button?.title = "🤖 \(rem)%"
        } else {
            statusItem.button?.title = "🤖 ?"
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
        nohup "\(kPythonPath)" "\(kProjectDir)/dashboard.py" --serve --port \(port) --no-open \
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
        } catch { /* 忽略：python 缺失等 */ }
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
        menu.addItem(withTitle: "🔄 刷新限额", action: #selector(menuRefresh), keyEquivalent: "r").target = self
        menu.addItem(withTitle: "📊 展开为看板", action: #selector(menuDash), keyEquivalent: "d").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "退出", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        if let button = statusItem.button {
            menu.popUp(positioning: nil, at: NSPoint(x: 0, y: button.bounds.height + 4), in: button)
        }
    }

    @objc private func menuRefresh() { refreshQuota() }
    @objc private func menuDash() { openDashboard() }
}

// MARK: - 启动

let app = NSApplication.shared
app.setActivationPolicy(.accessory)   // 不进 Dock，只在菜单栏
let controller = AppController()
app.delegate = controller
app.run()
