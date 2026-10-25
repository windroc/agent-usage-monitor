# TASK-583：显式 `CLAUDE_CONFIG_DIR` 账号的 `claude -p /usage` 实测

**结论**：`<dir-b>` 通过；`<dir-a>` 未通过。

| 通过条件 | `<dir-a>` | `<dir-b>` |
|---|---|---|
| 1. `claude auth status` 已登录 | 通过 | 通过 |
| 2. 含 5h、7d 百分比和重置时间 | **未通过**：缺 5h 重置时间 | 通过 |
| 3. 探测会话无新增 `message.usage` 行 | 通过 | 通过 |
| 4. 不触发 hooks、MCP（模型上下文协议）server | 通过 | 通过 |

`<dir-a>` 本周额度已用完，`Current session` 为 0%，CLI 没有输出 5h 重置行。未经验证的推断：没有进行中的 5h 窗口，与显式目录无关。

据此，M1 多账号沿用 FR-9 目前只对 `<dir-b>` 有实测依据。`<dir-a>` 要等周额度重置（Oct 18 6am，America/New_York）后复测：通过，则两个账号都沿用 FR-9；仍无 5h 重置时间，则按否定处理，非默认账号改用 status line tap（FR-30）或另定方案。仅验证 Claude Code `2.1.302`。

## 实测结果

2026-10-17，每个目录连续两次；5h 百分比仅供参考，额度判据是探测项目新增 `message.usage` 行。

| 观察 | A1（`<dir-a>`） | A2（`<dir-a>`） | B1（`<dir-b>`） | B2（`<dir-b>`） |
|---|---|---|---|---|
| 开始时间（UTC，协调世界时） | 16:00:31.785 | 16:00:34.212 | 16:00:36.540 | 16:00:38.971 |
| 耗时 / 退出码 | 1.146 秒 / 0 | 0.833 秒 / 0 | 1.153 秒 / 0 | 0.916 秒 / 0 |
| `claude auth status` | `loggedIn: true` | 同左 | `loggedIn: true` | 同左 |
| 5h / 7d（全部模型） | 0% / 100% | 同左 | 13% / 14% | 同左 |
| 5h 重置 | 无输出 | 无输出 | Oct 17 at 2:40pm | 同左 |
| 7d 重置 | Oct 18 at 6am | 同左 | Oct 24 at 1am | 同左 |
| 新增会话文件 / `message.usage` 行 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| `hook-ran` / `mcp-ran` | 均不存在 | 均不存在 | 均不存在 | 均不存在 |

重置时区均为 America/New_York。两个账号 `authMethod` 为 `claude.ai`，`apiProvider` 为 `firstParty`。stdout（标准输出）只有订阅提示、`Current session`、`Current week (all models)`、`Current week (Fable)` 四行，无历史贡献统计；stderr（标准错误）为空。现有 `claude_usage.parse` 能解析全部四份输出；`<dir-a>` 的 5h 窗口解析为 `used_percent 0`、`resets_at None`（`tests/test_claude_usage.py` 的 `test_config_dir_fixtures`）。

完整 stdout、stderr、文件清单及元数据：[`tests/fixtures/claude-usage-config-dir/`](../../tests/fixtures/claude-usage-config-dir/)，结构化记录见 [`observations.json`](../../tests/fixtures/claude-usage-config-dir/observations.json)。

## 参数与隔离

命令、探测目录准备、stdin（标准输入）、30 秒超时及哨兵与 [TASK-572 报告](TASK-572-claude-usage.md#最终参数与隔离) 相同（`quotaboard/claude.py` 的 `ARGS`、`_environment`、`_prepare`），每个账号各用一个探测目录。唯一差别：

| 环境项 | TASK-572 | 本次 |
|---|---|---|
| `CLAUDE_CONFIG_DIR` | 从环境移除 | 显式设为 `<dir-a>` 或 `<dir-b>` 的绝对路径 |

`claude auth status` 在同一环境、同一探测目录下运行。

## 文件与登录项

每次先 `touch <MARKER>`，结束后 `find <dir> <PROBE> -newer <MARKER> -type f`：

| 清单 | 文件数 | 内容 |
|---|---|---|
| [A1.find.txt](../../tests/fixtures/claude-usage-config-dir/A1.find.txt) | 231 | `.claude.json`、`backups/` 下其备份 1 份、`plugins/synced/` 3、`skills/synced/` 226 |
| [A2.find.txt](../../tests/fixtures/claude-usage-config-dir/A2.find.txt) | 3 | `.claude.json`、`skills/synced/` 2 |
| [B1.find.txt](../../tests/fixtures/claude-usage-config-dir/B1.find.txt) | 232 | `.claude.json`、`backups/` 下其备份 1 份、`plugins/synced/` 3、`skills/synced/` 227 |
| [B2.find.txt](../../tests/fixtures/claude-usage-config-dir/B2.find.txt) | 2 | `.claude.json`、`plugins/synced/` 1 |

- 每个目录第一次探测同步账号的插件和 skill（`synced/` 下）；第二次只改 `synced/` 下的 `.last-complete-round`，`<dir-a>` 另改 `skills/synced/` 的 `manifest.json`。
- `<dir>/.claude.json` 每次都被整体重写（inode（文件索引节点）变化），第一次变大，第二次大小不变；`<dir>/settings.json` 四次大小、修改时间和 inode 均不变。
- 新建空目录 `<dir>/projects/<PROBE_PROJECT>/memory/`，其中无文件；`<dir>/projects/` 下没有任何 `*.jsonl`。
- `<PROBE>` 无运行期间新建或改动文件。

登录项只看属性：`security dump-keychain`（不加 `-d`）列出服务名，`security find-generic-password -s <service>`（不加 `-w`）取属性。

| 账号 | 登录项服务名 | `mdat` |
|---|---|---|
| 默认（`CLAUDE_CONFIG_DIR` 未设置） | `Claude Code-credentials` | 四次探测前后均不变 |
| `<dir-a>`、`<dir-b>` | `Claude Code-credentials-<h>`，`<h>` 为该目录绝对路径 SHA-256 的前 8 位十六进制 | 每个目录两次探测前后均不变 |

两个目录的 `<h>` 均已按此规则核对；真实值由私有路径算出，不入库。

**推断**：TASK-572 把 `CLAUDE_CONFIG_DIR` 显式设成 `~/.claude` 时显示未登录，符合这一命名：显式设置后 CLI 查找带路径哈希的登录项，而默认账号的登录保存在不带后缀的项里。所以默认账号必须保持 `CLAUDE_CONFIG_DIR` 未设置（`quotaboard/claude.py` 现行做法）。

## 对 M1 的影响

| 需求 | 本轮依据 |
|---|---|
| FR-9 | `<dir-b>`：沿用本命令，另设 `CLAUDE_CONFIG_DIR=<dir>`；`<dir-a>`：待复测；默认账号不设 |
| FR-10 | 兼容没有 5h 重置行、也没有历史统计段的输出；现有解析已满足 |
| FR-30 | `<dir-b>` 不需要；`<dir-a>` 复测仍未通过时启用 |

脱敏使用 `<HOME>`、`<dir-a>`、`<dir-b>`、`<PROBE>`、`<PROBE_PROJECT>`、`<MARKER>`、`<ORG_ID>`、`<SYNC_ID>`；本轮 stdout 未出现邮箱、组织名等身份字段。真实目录名、邮箱、组织名、组织 ID 和路径哈希均不入库。

## 来源

- TASK-583：通过条件与记录项。
- [TASK-572 报告](TASK-572-claude-usage.md)：命令、环境与哨兵。
- [TASK-561 PRD](https://github.com/windroc/private_docs/blob/main/Product%20Design/2026-10-16-2312-TASK-561-m1-macos-widget.md)：下游需求背景。
