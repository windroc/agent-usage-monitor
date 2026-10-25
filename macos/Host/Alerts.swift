import Foundation

// FR-8: the alerts in `collect --emit-alerts` output. Foundation only, so macos/Tests can build it alone.

let alertPrefix = "AUM-ALERT "

private struct Payload: Decodable {
    let text: String
}

/// One alert: its text, and its line verbatim, which `record-alerts` gets back once macOS has it (TASK-640).
struct AlertLine: Equatable {
    let text: String
    let line: String
}

/// Each `AUM-ALERT {"text": …}` line, in order; any other line (login-shell output) is skipped.
func alertLines(_ output: Data) -> [AlertLine] {
    String(decoding: output, as: UTF8.self).split(whereSeparator: \.isNewline).compactMap { line in
        guard line.hasPrefix(alertPrefix),
              let payload = try? JSONDecoder().decode(Payload.self, from: Data(line.dropFirst(alertPrefix.count).utf8))
        else { return nil }
        return AlertLine(text: payload.text, line: String(line))
    }
}
