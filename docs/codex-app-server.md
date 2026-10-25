# Codex `app-server` rate-limit read

How `agent-usage-monitor collect` reads a Codex account's limits ([`agent_usage_monitor/codex.py`](../agent_usage_monitor/codex.py)), and what was checked on 2026-10-17 with codex-cli 0.163.0.

## Protocol

Source: `codex app-server generate-json-schema --out <dir>` (`ClientRequest.json`, `ClientNotification.json`, `v2/GetAccountRateLimitsResponse.json`), confirmed by one real reply ([`tests/fixtures/codex-app-server/rate-limits-read.jsonl`](../tests/fixtures/codex-app-server/rate-limits-read.jsonl), identifiers replaced with placeholders).

`codex app-server` with `CODEX_HOME=<dir>` speaks JSON-RPC over stdio, one JSON object per line, without a `"jsonrpc"` field. agent-usage-monitor sends exactly:

```
{"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "agent-usage-monitor", "version": "0.1.0"}}}
{"method": "initialized"}
{"id": 2, "method": "account/rateLimits/read"}
```

The server may send notifications (for example `remoteControl/status/changed`) before a response; agent-usage-monitor skips every message that is not the awaited response. No turn or thread is started.

The response's `result.rateLimits` holds `primary` and `secondary`, each `null` or `{"usedPercent", "windowDurationMins", "resetsAt"}` (`resetsAt` in epoch seconds). agent-usage-monitor maps windows by duration, not by slot: 300 minutes is `five_hour`, 10080 is `seven_day`. Any other duration, or two windows of one duration, makes the reply unrecognized.

## A window the account does not have

The real reply for one account had only a weekly window (`primary` 10080 minutes, `secondary: null`). agent-usage-monitor stores such a window as `null` in the snapshot ("no such limit"), distinct from `{"used_percent": null, "resets_at": null}` ("unknown"), and judges availability only on the windows the account has.

## `auth.json` check (PRD step 2)

With Codex sessions running on the same `CODEX_HOME`, one `app-server` read left `auth.json` unchanged: `stat -f '%m %i %z'` printed the same modification time, inode and size before and after (the file was not opened). agent-usage-monitor therefore probes accounts even while a session uses them; the PRD's FR-32 (skip accounts with a running session) is not needed.
