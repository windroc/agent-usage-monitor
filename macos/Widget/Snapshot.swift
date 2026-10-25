import Foundation

// Snapshot model and widget layout (FR-27; TASK-595 bars replace FR-26 text rows). Foundation only, so macos/Tests can build it alone.

struct UsageWindow: Decodable, Equatable {
    let usedPercent: Int?
    let resetsAt: Int?
}

struct Row: Decodable, Equatable {
    let name: String
    let client: String?
    let account: String?
    let available: Bool?
    let fiveHour: UsageWindow?
    let sevenDay: UsageWindow?
    let source: String?
    let stale: Bool?
    /// TASK-873: `claude` reports the account logged out; absent in snapshots from before it.
    var needsLogin: Bool? = nil
}

struct Snapshot: Decodable, Equatable {
    let generatedAt: Int
    let accounts: [Row]
}

enum Level: Equatable {
    case normal, warn, critical, unknown
}

struct Bar: Equatable {
    let label: String
    let percent: Int?
    var reset: String? = nil

    var text: String { percent.map { "\($0)%" } ?? "—" }
    var level: Level {
        guard let p = percent else { return .unknown }
        return p >= 90 ? .critical : p >= 80 ? .warn : .normal
    }
}

/// The fill colour; the widget maps it to a SwiftUI colour.
enum Hue: Equatable {
    case teal, periwinkle, gray, yellow, red
}

/// nil for an unknown percent (track only). ≥80 and ≥90 override the client's base colour.
func hue(client: String?, level: Level) -> Hue? {
    switch level {
    case .unknown: return nil
    case .critical: return .red
    case .warn: return .yellow
    case .normal: return client == "claude" ? .teal : client == "codex" ? .periwinkle : .gray
    }
}

/// At least the bar height when percent > 0, so 1% still shows a dot.
func fillWidth(percent: Int?, track: Double, height: Double) -> Double {
    guard let p = percent, p > 0 else { return 0 }
    return min(track, max(height, track * Double(min(p, 100)) / 100))
}

struct DisplayRow: Equatable {
    let title: String
    let client: String?
    var account: String? = nil
    let bars: [Bar]
    /// Shown instead of the bars (needs login); the row keeps its heights.
    var notice: String? = nil

    /// The bar whose reset line also carries the account, on its left: the last one with a reset.
    var accountBar: Int? { account == nil ? nil : bars.lastIndex { $0.reset != nil } }
    /// No reset line to share: the account takes a line of its own under the last bar.
    var accountLine: Bool { account != nil && accountBar == nil }
    /// Compact (medium): the line under the bars, with the account on its left and each reset under its own bar.
    var secondLine: Bool { account != nil || bars.contains { $0.reset != nil } }
}

struct Display: Equatable {
    let rows: [DisplayRow]
    let more: Int
}

/// Heights in points; the widget draws window rows, dividers and the +k line at exactly these.
enum Metrics {
    static let row = 22.0
    static let reset = 14.0 // the line and a 2 pt gap before the next row; also the account's own line
    static let divider = 11.0
    static let more = 14.0
    static let compactDivider = 7.0 // medium: 3 accounts with their second lines fit 155 pt less 16 pt margins
}

/// A logged-out account's notice: what to do, short enough for medium's bar columns.
let loginNotice = "needs login · claude /login"

/// `resets: 38m` / `2h 9m` / `6d 1h 1m`, leading zero units left out; nil when null or not in the future.
func resetText(_ resetsAt: Int?, now: Int) -> String? {
    guard let at = resetsAt, at > now else { return nil }
    let m = max(1, (at - now) / 60)
    let units = [(m / 1440, "d"), (m % 1440 / 60, "h"), (m % 60, "m")].drop { $0.0 == 0 }
    return "resets: " + units.map { "\($0.0)\($0.1)" }.joined(separator: " ")
}

// agent_usage_monitor/store.py SCHEMA; another version may reuse field names with other meanings.
let snapshotSchema = 1

private struct Versioned: Decodable {
    let schema: Int
}

/// nil when the file is missing, unreadable, not a snapshot or another schema version.
func loadSnapshot(path: String) -> Snapshot? {
    guard let data = FileManager.default.contents(atPath: path) else { return nil }
    let decoder = JSONDecoder()
    decoder.keyDecodingStrategy = .convertFromSnakeCase
    guard (try? decoder.decode(Versioned.self, from: data))?.schema == snapshotSchema else { return nil }
    return try? decoder.decode(Snapshot.self, from: data)
}

func rows(_ snapshot: Snapshot, now: Int) -> [DisplayRow] {
    // A null window (the account has no such limit) gets no row. ⚠ leads: a long title loses its tail, not the ⚠.
    // The title is the client; the name stands in only for a row without one.
    // Needs login: its last values say nothing until then, so the notice replaces the bars and the ⚠ (TASK-873).
    snapshot.accounts.map { row in
        if row.needsLogin == true {
            return DisplayRow(title: row.client ?? row.name, client: row.client, account: row.account, bars: [],
                              notice: loginNotice)
        }
        return DisplayRow(title: (row.stale == true ? "⚠ " : "") + (row.client ?? row.name), client: row.client,
                          account: row.account,
                          bars: [("5H", row.fiveHour), ("7D", row.sevenDay)].compactMap { label, window in
                              window.map {
                                  Bar(label: label, percent: $0.usedPercent, reset: resetText($0.resetsAt, now: now))
                              }
                          })
    }
}

/// nil, the FR-27 no-data view, when there is no snapshot or it has no accounts.
func content(_ snapshot: Snapshot?, now: Int) -> [DisplayRow]? {
    guard let s = snapshot, !s.accounts.isEmpty else { return nil }
    return rows(s, now: now)
}

/// +k sits under the last visible title; it needs a line of its own only when that spot is taken,
/// by the title itself or by the account on the last line.
func moreRoom(_ last: DisplayRow) -> Double {
    if last.accountLine || (last.accountBar != nil && last.accountBar == last.bars.count - 1) { return Metrics.more }
    return last.bars.count > 1 || last.bars.first?.reset != nil ? 0 : Metrics.more
}

/// Compact: +k takes the left of the second line, unless the account is there or there is no second line.
func compactMoreRoom(_ last: DisplayRow) -> Double {
    last.account != nil || !last.secondLine ? Metrics.more : 0
}

/// The leading accounts that fit `height`, leaving room for +k on overflow. Compact: one bar line per account.
func fit(_ rows: [DisplayRow], height: Double, compact: Bool = false) -> Display {
    func span(_ row: DisplayRow) -> Double {
        if compact { return Metrics.row + (row.secondLine ? Metrics.reset : 0) }
        return (row.bars.isEmpty ? Metrics.row : row.bars.reduce(0) { $0 + Metrics.row + ($1.reset == nil ? 0 : Metrics.reset) })
            + (row.accountLine ? Metrics.reset : 0)
    }
    func used(_ n: Int) -> Double {
        rows.prefix(n).reduce(0) { $0 + span($1) } + Double(max(0, n - 1)) * (compact ? Metrics.compactDivider : Metrics.divider)
    }
    if used(rows.count) <= height { return Display(rows: rows, more: 0) }
    var n = 0
    while n < rows.count && used(n + 1) + (compact ? compactMoreRoom(rows[n]) : moreRoom(rows[n])) <= height { n += 1 }
    return Display(rows: Array(rows.prefix(n)), more: rows.count - n)
}
