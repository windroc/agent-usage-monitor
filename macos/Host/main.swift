import AppKit
import SwiftUI
import UserNotifications
import WidgetKit

// FR-23, FR-24: run `agent-usage-monitor collect`, refresh the widget, exit. M2 FR-8: post the alerts it prints,
// then record the ones macOS took (TASK-640). TASK-645: opened by the user, show the settings window instead;
// TASK-654: also for the widget gear's URL.

let collectTimeout: TimeInterval = 40
let killGrace: TimeInterval = 2
// reloadAllTimelines is fire-and-forget XPC; give it a moment before exiting.
let exitDelay: TimeInterval = 2
// After collect exits, a stray child of the login shell may still hold its stdout open.
let outputGrace: TimeInterval = 2
// The first alert waits on the user's answer to macOS's Allow prompt. With collect (40 + 2 + 2 s), the adds,
// record-alerts (20 + 2 s) and exitDelay the host ends by about 268 s, before the LaunchAgent's next run at 300 s.
let authTimeout: TimeInterval = 180
let addTimeout: TimeInterval = 20
let recordTimeout: TimeInterval = 20
let settingsTimeout: TimeInterval = 20
// launchd's runs exit while this host shows the window (one host at a time), so the window's host collects as often.
let settingsRefresh: TimeInterval = 300
let settingsHint = "turn them on in System Settings › Notifications › Agent Usage Monitor"
let logPath = NSHomeDirectory() + "/Library/Logs/agent-usage-monitor.log"

/// FR-8: alert send failures go to the log file, also when a widget click (not launchd) started the host.
func logLine(_ line: String) {
    let data = Data("agent-usage-monitor host: \(line)\n".utf8)
    guard let log = FileHandle(forWritingAtPath: logPath) else {
        FileHandle.standardError.write(data)
        return
    }
    log.seekToEndOfFile()
    log.write(data)
    log.closeFile()
}

/// collect's stdout, read on a background thread until EOF.
final class Output {
    private let lock = NSLock()
    private var data = Data()
    let eof = DispatchGroup()

    func append(_ chunk: Data) {
        lock.lock()
        data.append(chunk)
        lock.unlock()
    }

    var bytes: Data {
        lock.lock()
        defer { lock.unlock() }
        return data
    }
}

/// One delivery's completion, run once: by the last add, a refusal or a timeout; passes the lines macOS took.
final class Delivery {
    var done: (([String]) -> Void)?
    var granted = false
    var sent: [String] = []

    func finish(_ problem: String?) {
        guard let done = done else { return }
        self.done = nil
        if let problem = problem { logLine(problem) }
        done(sent)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, UNUserNotificationCenterDelegate {
    private var pendingClick = false
    private var pendingRetry = false
    private var timedOut = false
    private var running = false
    private var launched = false
    private var openedURLs: [URL] = []
    private var settings: NSWindow?
    private var settingsTimer: Timer?
    private let model = SettingsModel()

    func applicationDidFinishLaunching(_ notification: Notification) {
        UNUserNotificationCenter.current().delegate = self
        launched = true
        open(xpcServiceName: ProcessInfo.processInfo.environment["XPC_SERVICE_NAME"], urls: openedURLs)
    }

    // A widget click (its widgetURL, or the gear's settings URL): on a cold launch this comes before
    // applicationDidFinishLaunching.
    func application(_ application: NSApplication, open urls: [URL]) {
        if launched { open(xpcServiceName: nil, urls: urls) } else { openedURLs += urls }
    }

    private func open(xpcServiceName: String?, urls: [URL]) {
        if opensSettings(xpcServiceName: xpcServiceName, urls: urls) {
            showSettings()
        } else {
            refresh(retryPaused: retriesPaused(urls: urls))
        }
    }

    // While this host runs, opening the app from Finder, Spotlight or the Dock arrives as a reopen; a widget click
    // arrives as a URL only.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showSettings()
        return false
    }

    // Show alerts as banners even if a widget click made this app active.
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list])
    }

    /// A click during a run that did not retry makes the next run retry.
    private func refresh(retryPaused: Bool = false) {
        if running {
            pendingClick = true
            pendingRetry = pendingRetry || retryPaused
        } else {
            run(retryPaused: retryPaused)
        }
    }

    private func run(retryPaused: Bool) {
        running = true
        timedOut = false
        model.save.collectStarted()
        cli(collectArgs(retryPaused: retryPaused), timeout: collectTimeout) { status, output in
            self.timedOut = status == nil
            self.model.save.collectEnded(status)
            self.finished(output)
        }
    }

    /// Runs `agent-usage-monitor <args>`, passing its exit status (nil: did not start or ran over `timeout`) and stdout.
    /// Through `zsh -l` for the login PATH that has claude and codex, and so the settings window reads and writes the
    /// accounts.json that collect reads.
    private func cli(_ args: String, input: Data? = nil, timeout: TimeInterval, done: @escaping (Int32?, Data) -> Void) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/zsh")
        task.arguments = ["-l", "-c", "exec \"$HOME/.local/bin/agent-usage-monitor\" \(args)"]
        let pipe = Pipe()
        task.standardOutput = pipe
        let stdin = Pipe()
        if input != nil { task.standardInput = stdin }
        let output = Output()
        output.eof.enter()
        var ranOver = false
        task.terminationHandler = { task in
            DispatchQueue.global().async {
                _ = output.eof.wait(timeout: .now() + outputGrace)
                let bytes = output.bytes
                DispatchQueue.main.async { done(ranOver ? nil : task.terminationStatus, bytes) }
            }
        }
        do {
            try task.run()
        } catch {
            FileHandle.standardError.write(Data("agent-usage-monitor host: cannot start /bin/zsh: \(error)\n".utf8))
            done(nil, Data())
            return
        }
        if let input = input {
            try? stdin.fileHandleForWriting.write(contentsOf: input)
            try? stdin.fileHandleForWriting.close()
        }
        DispatchQueue.global().async {
            let reader = pipe.fileHandleForReading
            var chunk = reader.availableData
            while !chunk.isEmpty {
                output.append(chunk)
                chunk = reader.availableData
            }
            output.eof.leave()
        }
        let pid = task.processIdentifier
        DispatchQueue.main.asyncAfter(deadline: .now() + timeout) {
            guard task.isRunning else { return }
            ranOver = true
            let name = args.split(separator: " ").first ?? ""
            FileHandle.standardError.write(Data("agent-usage-monitor host: \(name) ran over \(Int(timeout)) s, stopping it\n".utf8))
            task.terminate()
            DispatchQueue.main.asyncAfter(deadline: .now() + killGrace) {
                if task.isRunning { kill(pid, SIGKILL) }
            }
        }
    }

    /// FR-8: hand every alert to macOS; pass on the lines of those it took. The rest stay unrecorded, so the next
    /// collect prints them again.
    private func deliver(_ alerts: [AlertLine], then done: @escaping ([String]) -> Void) {
        guard !alerts.isEmpty else { return done([]) }
        let delivery = Delivery()
        delivery.done = done
        DispatchQueue.main.asyncAfter(deadline: .now() + authTimeout) {
            guard !delivery.granted else { return }
            delivery.finish("no answer to the notification prompt within \(Int(authTimeout)) s; \(alerts.count) alert(s) "
                            + "kept for the next run; if no prompt shows, \(settingsHint)")
        }
        let center = UNUserNotificationCenter.current()
        center.requestAuthorization(options: [.alert]) { granted, error in
            DispatchQueue.main.async {
                // Already given up: posting now would repeat on the next run.
                guard delivery.done != nil else { return }
                guard granted else {
                    let reason = error.map { ": \($0)" } ?? ""
                    return delivery.finish("notifications not allowed\(reason); \(alerts.count) alert(s) kept for the next run; "
                                           + settingsHint)
                }
                delivery.granted = true
                DispatchQueue.main.asyncAfter(deadline: .now() + addTimeout) {
                    delivery.finish("\(alerts.count - delivery.sent.count) alert(s) not handed to macOS within "
                                    + "\(Int(addTimeout)) s; kept for the next run")
                }
                let group = DispatchGroup()
                for alert in alerts {
                    let content = UNMutableNotificationContent()
                    content.title = "Agent Usage Monitor"
                    content.body = alert.text
                    group.enter()
                    center.add(UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)) { error in
                        DispatchQueue.main.async {
                            if let error = error {
                                logLine("cannot post an alert, kept for the next run: \(error)")
                            } else {
                                delivery.sent.append(alert.line)
                            }
                            group.leave()
                        }
                    }
                }
                group.notify(queue: .main) { delivery.finish(nil) }
            }
        }
    }

    /// TASK-640: `record-alerts` records the lines macOS took in `notified`. No login shell: it needs no PATH.
    private func record(_ lines: [String], then done: @escaping () -> Void) {
        guard !lines.isEmpty else { return done() }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: NSHomeDirectory() + "/.local/bin/agent-usage-monitor")
        task.arguments = ["record-alerts"]
        let pipe = Pipe()
        task.standardInput = pipe
        task.terminationHandler = { _ in DispatchQueue.main.async(execute: done) }
        do {
            try task.run()
        } catch {
            logLine("cannot record \(lines.count) sent alert(s), the next run sends them again: \(error)")
            return done()
        }
        do {
            try pipe.fileHandleForWriting.write(contentsOf: Data(lines.map { $0 + "\n" }.joined().utf8))
            try pipe.fileHandleForWriting.close()
        } catch {
            logLine("cannot pass the sent alerts to record-alerts, the next run sends them again: \(error)")
        }
        let pid = task.processIdentifier
        DispatchQueue.main.asyncAfter(deadline: .now() + recordTimeout) {
            guard task.isRunning else { return }
            logLine("record-alerts ran over \(Int(recordTimeout)) s, stopping it")
            task.terminate()
            DispatchQueue.main.asyncAfter(deadline: .now() + killGrace) {
                if task.isRunning { kill(pid, SIGKILL) }
            }
        }
    }

    private func finished(_ output: Data) {
        WidgetCenter.shared.reloadAllTimelines()
        deliver(alertLines(output)) { sent in
            self.record(sent) {
                DispatchQueue.main.asyncAfter(deadline: .now() + exitDelay) {
                    let again = self.pendingClick && !self.timedOut
                    let retry = self.pendingRetry
                    self.pendingClick = false
                    self.pendingRetry = false
                    self.running = false
                    if again {
                        self.run(retryPaused: retry)
                    } else {
                        self.model.save.collectDropped()
                        if self.settings == nil { NSApp.terminate(nil) }
                    }
                }
            }
        }
    }

    /// FR-1: a regular app with a Dock icon while the window shows.
    private func showSettings() {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate()
        if let window = settings {
            window.makeKeyAndOrderFront(nil)
            return
        }
        NSApp.mainMenu = settingsMenu()
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 900, height: 420),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Agent Usage Monitor Settings"
        window.isReleasedWhenClosed = false
        let hosting = NSHostingView(rootView: SettingsView(model: model))
        window.contentView = hosting
        window.setContentSize(hosting.fittingSize)
        window.delegate = self
        window.center()
        window.makeKeyAndOrderFront(nil)
        settings = window
        settingsTimer = Timer.scheduledTimer(withTimeInterval: settingsRefresh, repeats: true) { _ in self.refresh() }
        model.onSave = { self.save() }
        cli("read-accounts", timeout: settingsTimeout) { status, output in
            if status == 0, let file = lastLine(AccountsFile.self, output) {
                self.model.show(file)
            } else {
                self.model.problem = "Can't run ~/.local/bin/agent-usage-monitor read-accounts"
                    + (status.map { " (exit \($0))" } ?? "") + "; run make install first"
            }
        }
    }

    /// FR-6 to FR-8: write-accounts checks and writes; a written list is collected at once.
    private func save() {
        guard let request = try? JSONEncoder().encode(model.request) else { return }
        model.clearProblems()
        model.save.saveStarted()
        cli("write-accounts", input: request, timeout: settingsTimeout) { status, output in
            self.model.save.saveEnded(written: status == 0)
            if status == 0 {
                self.refresh()
            } else if status == 1, let result = lastLine(SaveProblems.self, output) {
                self.model.failed(result.problems)
            } else {
                self.model.problem = "Save failed" + (status.map { " (exit \($0))" } ?? "") + "; the file is unchanged"
            }
        }
    }

    /// Text fields get Cmd+X, C, V, A and Z only from the main menu's key equivalents, and this app has no nib.
    private func settingsMenu() -> NSMenu {
        func item(_ title: String, _ action: Selector, _ key: String, _ mask: NSEvent.ModifierFlags = .command) -> NSMenuItem {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
            item.keyEquivalentModifierMask = mask
            return item
        }
        let quit = item("Quit Agent Usage Monitor", #selector(quit(_:)), "q")
        quit.target = self
        let menu = NSMenu()
        for (title, items) in [
            ("Agent Usage Monitor", [quit]),
            ("File", [item("Close Window", #selector(NSWindow.performClose(_:)), "w")]),
            ("Edit", [item("Undo", Selector(("undo:")), "z"), item("Redo", Selector(("redo:")), "z", [.command, .shift]),
                      .separator(), item("Cut", #selector(NSText.cut(_:)), "x"), item("Copy", #selector(NSText.copy(_:)), "c"),
                      item("Paste", #selector(NSText.paste(_:)), "v"), item("Select All", #selector(NSText.selectAll(_:)), "a")]),
        ] {
            let top = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            top.submenu = NSMenu(title: title)
            items.forEach { top.submenu?.addItem($0) }
            menu.addItem(top)
        }
        return menu
    }

    /// Quit goes the way of closing the window, so a running collect still records its alerts.
    @objc private func quit(_ sender: Any?) {
        if let window = settings { window.close() } else { NSApp.terminate(nil) }
    }

    /// FR-1: closing the window ends the app, once a running collect has handed its alerts to macOS.
    func windowWillClose(_ notification: Notification) {
        settings = nil
        settingsTimer?.invalidate()
        NSApp.setActivationPolicy(.accessory)
        if !running { NSApp.terminate(nil) }
    }
}

// One host at a time; the lowest pid stays so two hosts started together don't both exit.
let me = getpid()
if NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "")
    .contains(where: { $0.processIdentifier < me }) {
    exit(0)
}

// A record-alerts that exits before reading its stdin must fail the write, not kill the host.
signal(SIGPIPE, SIG_IGN)
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
