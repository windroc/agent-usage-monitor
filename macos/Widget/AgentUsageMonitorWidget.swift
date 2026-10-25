import OSLog
import SwiftUI
import WidgetKit

private let log = Logger(subsystem: "com.windroc.agent-usage-monitor", category: "widget")

struct Entry: TimelineEntry {
    let date: Date
    let rows: [DisplayRow]?
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> Entry {
        Entry(date: Date(), rows: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) {
        completion(entry())
    }

    // FR-28: one entry, next refresh 5 minutes from now.
    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        let e = entry()
        completion(Timeline(entries: [e], policy: .after(e.date.addingTimeInterval(300))))
    }

    private func entry() -> Entry {
        // In the sandbox NSHomeDirectory() is the container; the exception is relative to the real home.
        let home = String(cString: getpwuid(getuid())!.pointee.pw_dir)
        let path = home + "/.local/state/agent-usage-monitor/snapshot.json"
        let now = Date()
        guard let snapshot = loadSnapshot(path: path) else {
            // A fixed message: the path holds the user name, and the system log leaves the machine in a sysdiagnose.
            log.error("no snapshot at ~/.local/state/agent-usage-monitor/snapshot.json")
            return Entry(date: now, rows: nil)
        }
        return Entry(date: now, rows: content(snapshot, now: Int(now.timeIntervalSince1970)))
    }
}

struct AgentUsageMonitorView: View {
    let entry: Entry
    // The system appearance: the forced .dark below applies only to the content.
    @Environment(\.colorScheme) private var scheme
    @Environment(\.widgetFamily) private var family

    var body: some View {
        // A tap anywhere opens the host app with this URL (FR-28), which tells it from the user opening the app (TASK-645).
        Group {
            if let rows = entry.rows {
                // The accounts that fit the real content height, so the size is measured, not assumed per family.
                GeometryReader { g in
                    let compact = family == .systemMedium
                    AccountList(display: fit(rows, height: g.size.height, compact: compact), width: g.size.width, compact: compact)
                }
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Agent Usage Monitor: no data").font(.headline)
                    Text("click to refresh").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .overlay(alignment: .bottomTrailing) { CornerLinks() }
        .widgetURL(URL(string: "agent-usage-monitor://refresh"))
        .containerBackground(for: .widget) { CardBackground(systemDark: scheme == .dark) }
        .environment(\.colorScheme, .dark)
    }
}

/// TASK-654: the gear opens the settings window; the rest of the widget refreshes. TASK-874: the arrow left of it
/// refreshes too, so that shows. Right-aligned with the percents, just under the content in the bottom margin, clear
/// of the rounded corner: medium has no free row for them (3 accounts use 122 of 123 pt), so they take no account's
/// room in `fit`.
struct CornerLinks: View {
    private let size = 10.0
    private let gap = 2.0

    var body: some View {
        HStack(spacing: size) {
            link("arrow.clockwise", "agent-usage-monitor://refresh")
            link("gearshape", "agent-usage-monitor://settings")
        }
        .offset(y: size + gap)
    }

    private func link(_ symbol: String, _ url: String) -> some View {
        Link(destination: URL(string: url)!) {
            Image(systemName: symbol).font(.system(size: size)).foregroundStyle(.secondary)
        }
        .frame(width: size, height: size)
    }
}

/// On the desktop a material follows the system appearance and ignores the forced dark scheme,
/// so a light system gets an opaque dark card instead.
struct CardBackground: View {
    let systemDark: Bool

    var body: some View {
        if systemDark { Rectangle().fill(.thinMaterial) } else { Color(white: 0.11) }
    }
}

struct AccountList: View {
    let display: Display
    let width: CGFloat
    var compact = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(display.rows.indices, id: \.self) { i in
                if i > 0 { Divider().frame(height: compact ? Metrics.compactDivider : Metrics.divider) }
                let row = display.rows[i]
                if compact {
                    compactRow(row)
                } else {
                    if row.bars.isEmpty {
                        HStack(spacing: 8) {
                            title(row.title)
                            if let notice = row.notice { self.notice(notice) }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .frame(height: Metrics.row)
                    }
                    ForEach(row.bars.indices, id: \.self) { j in
                        let bar = row.bars[j]
                        HStack(spacing: 8) {
                            title(j == 0 ? row.title : "")
                            BarRow(bar: bar, client: row.client)
                        }
                        .frame(height: Metrics.row)
                        if let reset = bar.reset {
                            HStack(spacing: 8) {
                                if j == row.accountBar, let account = row.account { small(account) }
                                Spacer(minLength: 0)
                                small(reset).fixedSize()
                            }
                            .frame(height: Metrics.reset, alignment: .top)
                        }
                    }
                    if row.accountLine, let account = row.account {
                        small(account).frame(maxWidth: .infinity, alignment: .leading)
                            .frame(height: Metrics.reset, alignment: .top)
                    }
                }
            }
            if display.more > 0, let last = display.rows.last {
                Color.clear.frame(height: compact ? compactMoreRoom(last) : moreRoom(last))
            }
        }
        .overlay(alignment: .bottomLeading) {
            if display.more > 0 {
                Text("+\(display.more)").font(.caption).foregroundStyle(.secondary)
                    .frame(height: Metrics.more, alignment: .bottomLeading)
            }
        }
    }

    // Compact: just wider than `claude` in the title font (49 pt), so the bars get the rest;
    // while a stale row shows, wide enough for `⚠ claude` (67 pt), keeping the columns aligned.
    private var titleWidth: CGFloat {
        guard compact else { return width * 0.34 }
        return display.rows.contains { $0.title.hasPrefix("⚠") } ? 68 : 52
    }
    private let gap = 6.0
    /// Compact: the 5H and the 7D column, each a bar with its reset under its right end.
    private var slot: CGFloat { (width - titleWidth - 2 * gap) / 2 }

    /// Medium: the client, then 5H and 7D side by side in fixed columns; a missing window leaves its column empty.
    /// Under them the account on the left, running under 5H while 5H has no reset.
    @ViewBuilder private func compactRow(_ row: DisplayRow) -> some View {
        let bars = ["5H", "7D"].map { label in row.bars.first { $0.label == label } }
        HStack(spacing: gap) {
            title(row.title)
            if let notice = row.notice {
                self.notice(notice).frame(width: 2 * slot + gap, alignment: .leading)
            } else {
                ForEach(bars.indices, id: \.self) { j in
                    Group {
                        if let bar = bars[j] { BarRow(bar: bar, client: row.client, compact: true) } else { Color.clear }
                    }
                    .frame(width: slot)
                }
            }
        }
        .frame(height: Metrics.row)
        if row.secondLine {
            HStack(spacing: gap) {
                HStack(spacing: 4) {
                    if let account = row.account { small(account) }
                    Spacer(minLength: 0)
                    if let reset = bars[0]?.reset { small(reset).fixedSize() }
                }
                .frame(width: titleWidth + gap + slot)
                HStack(spacing: 0) {
                    Spacer(minLength: 0)
                    if let reset = bars[1]?.reset { small(reset).fixedSize() }
                }
                .frame(width: slot)
            }
            .frame(height: Metrics.reset, alignment: .top)
        }
    }

    private func title(_ s: String) -> some View {
        // The same size as the percent: who first, then the number.
        Text(s).font(.system(size: 15, weight: .bold)).lineLimit(1).truncationMode(.tail)
            .frame(width: titleWidth, alignment: .leading)
    }

    /// Needs login (TASK-873): yellow like a warning bar, where the bars would be.
    private func notice(_ s: String) -> some View {
        Text(s).font(.system(size: 13, weight: .semibold)).foregroundStyle(.yellow).lineLimit(1).truncationMode(.tail)
    }

    /// The reset time and the account: gray caption, a long account loses its tail.
    private func small(_ s: String) -> some View {
        Text(s).font(.caption2).foregroundStyle(.secondary).lineLimit(1).truncationMode(.tail)
    }
}

struct BarRow: View {
    let bar: Bar
    let client: String?
    var compact = false
    @Environment(\.widgetRenderingMode) private var mode

    private let height = 10.0

    var body: some View {
        HStack(spacing: compact ? 3 : 6) {
            Text(bar.label)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, compact ? 3 : 6)
                .padding(.vertical, 2)
                .background(.quaternary, in: Capsule())
            GeometryReader { g in
                Capsule().fill(.quaternary)
                    .overlay(alignment: .leading) {
                        Capsule().fill(fill)
                            .frame(width: fillWidth(percent: bar.percent, track: g.size.width, height: height))
                    }
                    .frame(height: height)
                    .frame(maxHeight: .infinity)
            }
            // Always reserved, so bars line up whether or not the glyph shows. Medium has none: its space goes to the bar.
            if !compact {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .opacity(bar.level == .critical ? 1 : 0)
                    .frame(width: 14)
            }
            // The hidden widest value keeps every bar the same length.
            ZStack(alignment: .trailing) {
                Text("100%").hidden()
                Text(bar.text).foregroundStyle(bar.percent == nil ? .secondary : .primary)
            }
            .font(.system(size: compact ? 13 : 15, weight: .bold, design: .rounded).monospacedDigit())
            .fixedSize()
        }
    }

    private var fill: AnyShapeStyle {
        if mode != .fullColor {
            return bar.level == .warn || bar.level == .critical ? AnyShapeStyle(.primary) : AnyShapeStyle(.secondary)
        }
        switch hue(client: client, level: bar.level) {
        case .teal?: return AnyShapeStyle(Color.teal)
        case .periwinkle?: return AnyShapeStyle(Color(red: 0x8E / 255, green: 0x8C / 255, blue: 0xFF / 255))
        case .gray?: return AnyShapeStyle(Color.gray)
        case .yellow?: return AnyShapeStyle(Color.yellow)
        case .red?: return AnyShapeStyle(Color.red)
        case nil: return AnyShapeStyle(Color.clear)
        }
    }
}

@main
struct AgentUsageMonitorWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "AgentUsageMonitor", provider: Provider()) { AgentUsageMonitorView(entry: $0) }
            .configurationDisplayName("Agent Usage Monitor")
            .description("Claude Code and Codex usage per account")
            .supportedFamilies([.systemMedium, .systemLarge])
    }
}
