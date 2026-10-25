# TASK-572：Claude `/usage` 实测

**结论**：按本 issue 最新观测判据，A 通过；M1 默认账号可用 A，不启用会话清理。B 未运行。仅验证 Claude Code `2.1.302`、默认登录账号、`CLAUDE_CONFIG_DIR` 未设置；不外推到显式账号目录或其他版本。

## 实测结果

2026-10-17，同一账号有其他会话并发使用。5h 百分比仅供参考，额度判据按用户最新决定改为探测项目新增 `message.usage` 行；不能据此证明所有版本、账号都绝不花额度。

| 观察 | A1 | A2 |
|---|---|---|
| 开始时间（UTC，协调世界时） | 05:07:24.915 | 05:07:46.861 |
| 耗时 / 退出码 | 7.576 秒 / 0 | 7.071 秒 / 0 |
| 5h / 7d（全部模型） | 17% / 1% | 17% / 1% |
| 5h 重置 | Oct 17 at 4:39am | 同左 |
| 7d 重置 | Oct 24 at 12:59am | 同左 |
| 重置时区 | America/New_York | 同左 |
| 探测项目新增会话文件 / `message.usage` 行 | 0 / 0 | 0 / 0 |
| `hook-ran` / `mcp-ran` | 均不存在 | 均不存在 |

输出还包含 Fable 周窗口及本机历史用量贡献统计。末尾的 `Top MCP servers` 是历史统计，不作为本次 MCP（模型上下文协议）server 启动证据。

完整 stdout（标准输出）、空 stderr（标准错误）、文件清单及元数据：[`tests/fixtures/claude-usage/`](../../tests/fixtures/claude-usage/)。结构化记录见 [`observations.json`](../../tests/fixtures/claude-usage/observations.json)。

## 最终参数与隔离

在专用空目录 `<PROBE>` 执行，stdin（标准输入）为 `/dev/null`，输出写文件（非终端），超时 30 秒：

```sh
claude -p --no-session-persistence --strict-mcp-config \
  --settings '{"remoteControlAtStartup":false,"disableAllHooks":true}' \
  --model sonnet --effort low /usage
```

| 环境项 | 本次值 |
|---|---|
| `CLAUDE_CONFIG_DIR` | 从环境移除；不显式指向默认目录 |
| `ANTHROPIC_*`、`CLAUDE_CODE_OAUTH_TOKEN` | 全部移除 |
| `DISABLE_AUTOUPDATER` | `1` |
| `PWD` | `<PROBE>` 的真实路径 |

`--model sonnet --effort low` 来自用户最新要求，优先于早先 PRD（产品需求文档）中不带 `--model` 的检查。

探测目录权限 0700；预置文件内容见结构化记录的 `probe_setup`。其中 `SessionStart` hook（钩子）和 stdio（标准输入输出）server 启动时分别 `touch` 两个哨兵。探测前后检查哨兵和探测项目目录；不执行清理、不改账号配置。

| 账号已有配置 | 观测 |
|---|---|
| `SessionStart`、`SessionEnd` 的 undead hook | 日志无新增字节，日志及 tab 注册文件元数据不变 |
| `PermissionRequest` 的终端通知 hook | 无可观测；没有独立日志或持久副作用 |
| `<CLAUDE_DIR>/settings.json`、默认全局配置的 `mcpServers` | 均无配置项 |

已有 hook 的观测位置来自本机只读源码：`<HOME>/.local/share/undead/lib/hook:13-16,36-59`、`common.zsh:7,14-18`；这些本机文件不随仓库分发。

## 文件与登录项

每次先 `touch <MARKER>`，结束后执行：

```sh
find <CLAUDE_DIR> <PROBE> -newer <MARKER> -type f
```

| 清单 | 文件数 | 范围 |
|---|---|---|
| [A1.find.txt](../../tests/fixtures/claude-usage/A1.find.txt) | 9 | 其他项目日志、插件同步标记、活动会话记录、历史文件 |
| [A2.find.txt](../../tests/fixtures/claude-usage/A2.find.txt) | 6 | 其他项目日志、插件同步标记、活动会话记录、全局配置备份 |

清单是时间窗口内的变化，不归因于探测。其他项目分别有 6、3 个既有会话文件变化，整个 `projects/` 均无新会话文件；并发项目不计入额度判据。`<PROBE>` 无运行期间新建或改动文件。探测项目的两次前后快照均无 `*.jsonl`；未逐次记录目录是否存在。

额外只看配置元数据：两次 `<CLAUDE_DIR>/settings.json`、`<CLAUDE_DIR>/.claude.json` 的大小、修改时间和 inode（文件索引节点）不变；`<HOME>/.claude.json` 两次均变化，无法区分探测与并发会话。前者与后者是不同文件；`find` 的账号目录范围不包括后者。

登录项仅执行 `security find-generic-password -s 'Claude Code-credentials'`，不加 `-w`，不取密码。四次属性快照的 `mdat` 均为 `2026-10-17T04:45:53Z`，未观测到修改时间变化；不据此保证没有任何其他登录项动作。脚本不读凭据文件、不直接调用 `api/oauth/usage`、不自行刷新 token（令牌）。

**历史记录**：用户报告 00:50 的早先探测创建了 `<CLAUDE_DIR>/.claude.json`，并使 `settings.json` 从 4772 变为 4776 字节。本次未复现实验，也没有修改或恢复这两个文件；历史数字不作为本轮实测证据。

## 对 M1 的影响

| 需求 | 本轮依据 |
|---|---|
| FR-9 | 采用本报告命令及适用范围 |
| FR-10 | 用两份完整输出测试 `Current session`、`Current week (all models)` 的百分比和重置时间；兼容附加 Fable 与历史统计段 |
| FR-29 | README 记录本报告的版本、默认账号限制和环境参数 |
| FR-30 | 本轮默认账号不需要回退到 status line tap（状态栏透传）；其他账号的行为仍未知 |

脱敏使用 `<HOME>`、`<CLAUDE_DIR>`、`<PROBE>`、`<PROBE_PROJECT>`、`<OTHER_PROJECT_n>`、`<SESSION_ID_n>`（`<OTHER_PROJECT_n>` 下的会话 ID）、`<ORG_ID>`、`<SYNC_ID>`（与 TASK-583 样本相同）；邮件地址若出现则替换为 `<EMAIL>`。组织名、登录名及账号目录名不得进入公开样本；本轮 stdout 未出现这些身份字段。

复核只需比对 fixture（测试样本）的窗口、退出状态、哨兵、探测项目和文件清单，解析结构化记录并检查脱敏；无需重复真实探测。

## 来源

- TASK-572：最新用户决定覆盖暂停及早先显式账号目录要求。
- [TASK-561 PRD](https://github.com/windroc/private_docs/blob/main/Product%20Design/2026-10-16-2312-TASK-561-m1-macos-widget.md)：下游需求背景。
- [官方命令参考](https://code.claude.com/docs/en/commands)：`/usage` 展示计划用量。[官方命令行参考](https://code.claude.com/docs/en/cli-reference)：`--no-session-persistence` 仅用于 print 模式及 `--strict-mcp-config` 的边界。文档未回答本机额度和文件副作用，故进行授权实测。
- CodexBar 固定版本 `6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e`：[直接探测](https://github.com/steipete/CodexBar/blob/6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e/Sources/CodexBarCore/Providers/Claude/ClaudeUsageFetcher.swift#L1179-L1202)、[临时设置](https://github.com/steipete/CodexBar/blob/6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e/Sources/CodexBarCore/Providers/Claude/ClaudeCLISession.swift#L405-L413)、[环境过滤](https://github.com/steipete/CodexBar/blob/6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e/Sources/CodexBarCore/Providers/Claude/ClaudeCLISession.swift#L455-L469)、[会话文件清理](https://github.com/steipete/CodexBar/blob/6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e/Sources/CodexBarCore/Providers/Claude/ClaudeProbeSessionArtifactCleaner.swift#L8-L59)。本轮未移植实现代码。
