import Foundation

// TASK-645: the settings window's data, as `read-accounts` prints it and `write-accounts` reads it. The rules live in
// agent_usage_monitor/accounts.py, the same ones collect reads the file with. Foundation only, so macos/Tests can build it.

/// FR-1, FR-2: a widget click opens the app with its widgetURL, launchd starts it with XPC_SERVICE_NAME set to the job
/// label; only LaunchServices (Finder, Spotlight, Dock, `open`) sets `application.<bundle id>.…` (observed on macOS 26,
/// not documented). TASK-654: the widget's gear opens it with `agent-usage-monitor://settings`. Anything else refreshes,
/// as before.
func opensSettings(xpcServiceName: String?, urls: [URL]) -> Bool {
    if urls.isEmpty { return xpcServiceName?.hasPrefix("application.") == true }
    return urls.contains { $0.scheme == "agent-usage-monitor" && $0.host == "settings" }
}

/// One account; `original` is its object in the file as JSON, so write-accounts keeps the keys the window does not show.
struct AccountRow: Codable, Identifiable, Equatable {
    var id = UUID()
    var name = ""
    var client = "claude"
    var dir = ""
    var account = ""
    var original = "{}"
    /// write-accounts' problem with this row; kept on the row so it moves with it.
    var problem: String?

    enum CodingKeys: String, CodingKey { case name, client, dir, account, original }
}

struct AccountsFile: Decodable {
    /// FR-9: the file cannot be shown; `accounts` then holds the defaults.
    let error: String?
    let threshold: Double
    let accounts: [AccountRow]
    let original: String
}

struct SaveRequest: Encodable {
    let threshold: Double
    let accounts: [AccountRow]
    let original: String
}

struct Problem: Decodable {
    /// The row, or nil for the threshold or the file as a whole.
    let index: Int?
    let message: String
}

struct SaveProblems: Decodable {
    let problems: [Problem]
}

/// TASK-676: the status line from Save to the end of the first collect that starts after the write, the one that reads
/// the new file. A collect already running then read the old file; a newer save outranks an older save's collect.
struct SaveStatus {
    private(set) var text = ""
    /// write-accounts is running; Save waits for it.
    private(set) var saving = false
    /// Written; the collect that reads the file has not started.
    private var waiting = false
    /// The running collect started after a save.
    private var collecting = false

    mutating func saveStarted() {
        saving = true
        text = "Saving…"
    }

    mutating func saveEnded(written: Bool) {
        saving = false
        waiting = written
        text = written ? "Saved, refreshing the widget…" : ""
    }

    mutating func collectStarted() {
        collecting = waiting
        waiting = false
    }

    /// `exit` is collect's status, nil when it ran over or did not start. Success clears the line.
    mutating func collectEnded(_ exit: Int32?) {
        guard collecting else { return }
        collecting = false
        if !waiting && !saving { text = exit == 0 ? "" : Self.failed(exit) }
    }

    /// No collect follows: the host dropped the rerun after one ran over.
    mutating func collectDropped() {
        guard waiting else { return }
        waiting = false
        if !saving { text = Self.failed(nil) }
    }

    /// The table no longer shows what was saved.
    mutating func edited() { text = "" }

    private static func failed(_ exit: Int32?) -> String {
        "Saved, but the widget refresh failed" + (exit.map { " (exit \($0))" } ?? " (timed out or didn't start)")
    }
}

/// The CLI prints one JSON line last; the login shell may print lines before it.
func lastLine<T: Decodable>(_ type: T.Type, _ output: Data) -> T? {
    guard let line = String(decoding: output, as: UTF8.self).split(whereSeparator: \.isNewline).last else { return nil }
    return try? JSONDecoder().decode(type, from: Data(line.utf8))
}
