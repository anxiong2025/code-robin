# Claude Code — 核心架构深度分析

> Anthropic 官方 Claude Code CLI 工具源码架构分析
>
> 项目规模：1,884 个 TypeScript 文件，512,664 行代码

---

# 目录

- [技术栈](#技术栈)
- [核心架构层次](#核心架构层次)
- [六大核心子系统](#六大核心子系统)
  - [1. 入口与启动](#1-入口与启动)
  - [2. 查询引擎 QueryEngine](#2-查询引擎-queryengine)
  - [3. 工具系统](#3-工具系统)
  - [4. 命令系统](#4-命令系统)
  - [5. 权限系统](#5-权限系统)
  - [6. 多智能体协调](#6-多智能体协调)
- [QueryEngine 深入分析](#queryengine-深入分析)
  - [类结构与公共 API](#类结构与公共-api)
  - [Tool-call 循环（核心状态机）](#tool-call-循环核心状态机)
  - [流式处理与 Token 管理](#流式处理与-token-管理)
  - [5 级上下文压缩管道](#5-级上下文压缩管道)
  - [错误恢复机制](#错误恢复机制)
  - [结果生成](#结果生成)
- [关键架构模式](#关键架构模式)
- [数据流概览](#数据流概览)

---

# 技术栈

| 层面 | 技术 |
|------|------|
| 语言 | TypeScript (strict mode) |
| 运行时 | Bun |
| 终端 UI | React + Ink |
| CLI 解析 | Commander.js |
| Schema 校验 | Zod v4 |
| API 客户端 | @anthropic-ai/sdk |
| 代码搜索 | ripgrep |
| 遥测 | OpenTelemetry + gRPC |
| 特性开关 | GrowthBook + bun:bundle 编译期消除 |

---

# 核心架构层次

```
┌─────────────────────────────────────────────────────────┐
│                   入口层 (main.tsx)                       │
│          Commander.js CLI → React/Ink 渲染器              │
├─────────────────────────────────────────────────────────┤
│               查询引擎 (QueryEngine.ts)                   │
│      LLM API 调用 · 流式响应 · Tool-call 循环             │
├──────────┬──────────┬───────────┬───────────────────────┤
│  命令系统  │  工具系统  │  技能系统   │      插件系统       │
│ commands/ │  tools/  │  skills/  │     plugins/          │
├──────────┴──────────┴───────────┴───────────────────────┤
│                    服务层 (services/)                      │
│   API · MCP · OAuth · LSP · Analytics · Compact          │
├─────────────────────────────────────────────────────────┤
│                     基础设施层                             │
│   hooks/ · utils/ · state/ · schemas/ · bridge/          │
└─────────────────────────────────────────────────────────┘
```

---

# 六大核心子系统

## 1. 入口与启动

**文件：** `src/main.tsx` — 803K 行

- Commander.js 定义 CLI 参数和子命令
- **并行预取优化**：启动时同时发起 MDM 配置读取、macOS Keychain 预取、API 预连接
- 初始化 GrowthBook 特性开关、OAuth 认证
- 创建 React/Ink 渲染器进入交互循环

---

## 2. 查询引擎 QueryEngine

**文件：** `src/services/QueryEngine.ts` — 46,630 行

项目**最核心**的文件，负责：

- 调用 Anthropic LLM API（流式响应）
- Tool-call 循环：LLM 返回工具调用 → 执行工具 → 结果送回 LLM → 循环直到完成
- Thinking mode 管理（extended thinking）
- Token 计数与成本追踪
- 上下文压缩触发

---

## 3. 工具系统

**目录：** `src/tools/` — ~40 个工具

每个工具是自包含模块，包含：

- 输入 Schema（Zod 校验）
- 权限模型（决定是否需要用户确认）
- 执行逻辑
- 进度状态类型

### 核心工具分类

| 类别 | 工具 |
|------|------|
| 文件操作 | BashTool, FileReadTool, FileWriteTool, FileEditTool |
| 搜索 | GlobTool, GrepTool, WebSearchTool, WebFetchTool |
| 智能体 | AgentTool (子智能体), SendMessageTool (智能体间通信) |
| 任务管理 | TaskCreate / TaskUpdate / TaskList / TaskGet |
| 协议集成 | MCPTool, LSPTool |
| 模式控制 | EnterPlanModeTool, EnterWorktreeTool |

---

## 4. 命令系统

**目录：** `src/commands/` — ~50 个斜杠命令

用户通过 `/command` 触发，覆盖：

- **Git 操作**：`/commit`, `/commit-push-pr`
- **代码审查**：`/review`, `/ultrareview`, `/autofix-pr`
- **上下文管理**：`/compact`, `/context`
- **配置管理**：`/config`, `/mcp`, `/memory`
- **会话管理**：`/resume`, `/share`, `/cost`

---

## 5. 权限系统

**目录：** `src/hooks/toolPermission/`

每次工具调用都经过权限检查，支持多种模式：

| 模式 | 行为 |
|------|------|
| `default` | 交互式提示用户确认 |
| `plan` | Plan 模式，自动批准读操作 |
| `bypassPermissions` | 全部自动批准 |
| `auto` | 基于分类器的自动审批 |

---

## 6. 多智能体协调

**目录：** `src/coordinator/` + `src/tools/AgentTool/`

- 通过 AgentTool 生成子智能体（独立进程）
- 子智能体拥有各自的工具集和权限范围
- SendMessageTool 实现智能体间通信
- `coordinator/` 目录管理多智能体编排

---

# QueryEngine 深入分析

QueryEngine 是整个系统最核心的文件，分为两部分：

- `src/QueryEngine.ts` (~1,295 行) — 类定义、状态管理、公共 API
- `src/services/query.ts` (~1,729 行) — 查询循环、流式处理、压缩管道

---

## 类结构与公共 API

```typescript
class QueryEngine {
  // 跨 turn 持久状态
  private mutableMessages: Message[]          // 完整对话历史
  private totalUsage: NonNullableUsage        // 累积 token 用量
  private permissionDenials: SDKPermissionDenial[]  // 工具拒绝记录
  private readFileState: FileStateCache       // 文件变更追踪
  private abortController: AbortController    // turn 取消控制

  // 公共方法
  async *submitMessage(prompt, options?)  // 主入口，返回 AsyncGenerator<SDKMessage>
  interrupt()                              // 中断当前查询
  getMessages() / getSessionId() / setModel()  // 访问器
}
```

### QueryEngineConfig 关键配置

- `tools`, `commands`, `mcpClients` — 工具/命令/MCP 目录
- `canUseTool` — 权限回调
- `getAppState` / `setAppState` — 状态管理
- `thinkingConfig` — 扩展思考控制
- `maxTurns` / `maxBudgetUsd` / `taskBudget` — 执行限制

---

## Tool-call 循环（核心状态机）

```
submitMessage(prompt)
  ├── processUserInput(prompt) → 处理斜杠命令、变更消息
  ├── recordTranscript() → 持久化（支持 --resume）
  │
  └── query() 主循环 ─── while(true) ───┐
      │                                  │
      ├── [1] 压缩管道                    │
      │   ├── 内容替换（超大工具结果裁剪） │
      │   ├── Snip compact（删除旧消息）  │
      │   ├── Microcompact（缓存编辑）    │
      │   ├── Context collapse（上下文折叠）│
      │   └── Autocompact（自动摘要压缩） │
      │                                  │
      ├── [2] callModel() 流式循环        │
      │   ├── 流式接收 LLM 响应           │
      │   ├── 收集 tool_use blocks        │
      │   ├── 流式工具执行器并行执行工具   │
      │   └── 实时轮询已完成的工具结果     │
      │                                  │
      ├── [3] 后处理与恢复                │
      │   ├── prompt-too-long → 响应式压缩 │
      │   ├── max_output_tokens → 3级恢复  │
      │   └── stop hooks 检查             │
      │                                  │
      ├── [4] 工具结果收集                │
      ├── [5] 附件（记忆、技能发现）       │
      ├── [6] turnCount++ & 限制检查      │
      │                                  │
      └── needsFollowUp? ────────────────┘
          ├── true  → 带工具结果继续循环
          └── false → 退出，生成最终结果
```

---

## 流式处理与 Token 管理

### Token 追踪三阶段

1. `message_start` → 记录 `input_tokens`（初始计数）
2. `message_delta` → 累积 `output_tokens`（流式增量）
3. `message_stop` → 汇总到 `totalUsage`（全局累积）

### Token 预算系统

- `taskBudget` — API 级别任务预算（跨 compact 保持）
- `TOKEN_BUDGET` 特性开关 → `checkTokenBudget()` 每轮检查
- 超限时触发继续提示或提前停止

---

## 5 级上下文压缩管道

| 阶段 | 机制 | 特性开关 |
|------|------|----------|
| 1. 内容替换 | 裁剪超大工具结果 | 默认启用 |
| 2. Snip | 删除旧消息释放空间 | `HISTORY_SNIP` |
| 3. Microcompact | 缓存编辑删除旧写入 | `CACHED_MICROCOMPACT` |
| 4. Context collapse | 上下文折叠 | `CONTEXT_COLLAPSE` |
| 5. Autocompact | 阈值触发完整摘要压缩 | 默认启用 |

**恢复路径（当 prompt-too-long 时）：**

1. 尝试 context collapse 排空
2. 尝试响应式 compact（完整摘要）
3. 都失败 → 上报错误

---

## 错误恢复机制

### Max Output Tokens 3 级升级

1. **Slot 升级**：8k → 64k（一次性）
2. **多轮恢复**：注入 `"Resume directly..."` 消息，最多重试 3 次
3. **耗尽**：上报错误

### 模型降级

- `FallbackTriggeredError` → 切换到 `fallbackModel`
- 清理孤儿 `tool_use` blocks（添加 tombstone）
- 剥离 thinking signatures（模型绑定）后重试

### 权限拒绝处理

- `wrappedCanUseTool` 包装器收集所有拒绝记录
- 孤儿权限恢复（上次被拒绝的工具的处理）
- 最终结果中报告 `permission_denials[]`

---

## 结果生成

| 类型 | 含义 |
|------|------|
| `success` | 正常完成，含文本结果、用量、成本 |
| `error_during_execution` | 运行时错误 |
| `error_max_turns` | 超过最大轮次 |
| `error_max_budget_usd` | 超过预算限制 |
| `error_max_structured_output_retries` | 结构化输出重试耗尽 |

---

# 关键架构模式

## 编译期特性开关

```typescript
const voiceCommand = feature('VOICE_MODE') ? require('./commands/voice') : null
// 构建时整个模块被消除，减小产物体积
```

已知开关：`PROACTIVE`, `KAIROS`, `BRIDGE_MODE`, `DAEMON`, `VOICE_MODE`, `COORDINATOR_MODE` 等

## 懒加载

OpenTelemetry、gRPC、Analytics 等重模块通过动态 `import()` 按需加载

## Memoization

系统/用户上下文在会话期间通过 `memoize()` 缓存，避免重复计算

## IDE 桥接 (`src/bridge/`)

与 VS Code / JetBrains 扩展双向通信：

- JWT 认证
- REPL 会话桥接
- 权限回调委托给 IDE

## 持久化记忆 (`src/memdir/`)

文件级记忆系统，跨会话持久化用户偏好、项目上下文、反馈等

---

# 数据流概览

```
用户输入 → Commander.js 解析
         → React/Ink 渲染层
         → QueryEngine 发送至 Claude API
         → Claude 返回 tool_use
         → 权限系统检查
         → 工具执行（Bash/文件/搜索/子智能体...）
         → 结果返回 QueryEngine
         → 循环直到 Claude 返回文本响应
         → Ink 渲染输出给用户
```

---

# 总结

Claude Code 的核心是一个 **Tool-call 驱动的智能体循环**，以 QueryEngine 为中枢，通过可扩展的工具/命令/技能/插件四层体系实现功能扩展。

QueryEngine 本身是一个精密的状态机，关键设计：

- **流式工具执行**：工具在 LLM 流式输出期间并行执行，而非等待完成后串行执行
- **5 级压缩管道**：从轻量裁剪到完整摘要，渐进式管理上下文窗口
- **3 级输出恢复**：slot 升级 → 多轮恢复 → 上报，最大化输出完整性
- **模型降级**：主模型失败时自动切换备用模型并清理状态
- **权限包装**：每次工具调用都经过权限检查，拒绝记录全程追踪
