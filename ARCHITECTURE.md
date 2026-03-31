# claude-code-robin 项目架构文档

![](https://fisherai-1312281807.cos.ap-guangzhou.myqcloud.com/e5ccbf0d9b6a5440cd550c8f99beceda.png)

## 快速开始

### 安装

```bash
# 从源码安装
git clone https://github.com/anxiong2025/claude-code-robin.git
cd claude-code-robin
pip install -e .

# 或直接运行（无需安装）
python3 -m src.main scan ./src
```

### 启动示例

```bash
# 扫描项目结构
claude-code-robin scan ./my-project

# 生成完整架构报告
claude-code-robin arch ./my-project

# 输出到文件
claude-code-robin arch ./my-project -o ARCHITECTURE.md

# 分析模块依赖
claude-code-robin deps ./my-project

# 项目统计
claude-code-robin stats ./my-project

# 交互模式（支持 Claude AI 对话）
claude-code-robin interactive
```

### 运行测试

```bash
# 全部测试
python3 -m unittest discover -s tests -v

# 单个测试
python3 -m unittest tests.test_porting_workspace.ScannerTests.test_scan_finds_python_files
```

### 交互模式使用

```
$ claude-code-robin interactive
claude-code-robin — Interactive Mode
Read your codebase like Robin reads Poneglyphs.

robin> scan ./src                                # 扫描项目
robin> deps ./src                                # 查看依赖
robin> stats ./src                               # 查看统计
robin> 这个项目使用了什么设计模式？                   # → Claude AI 对话
robin> exit                                      # 退出
```

> **注意：** 交互模式中的 Claude 对话需要设置 `ANTHROPIC_API_KEY` 环境变量，或配置 AWS Bedrock。

---

## 1. 项目概述

**claude-code-robin** — Python 项目架构分析器和文档生成器。

灵感来自 One Piece 的 Nico Robin —— 考古学家，专门阅读历史正文（Poneglyphs）解析隐藏结构。这个工具做的事情一样：**扫描你的代码，解析它的结构，生成可读的架构文档**。

**核心能力：**
- 递归扫描 Python 项目，统计文件、行数、模块
- AST 解析提取模块间 import 依赖关系
- 生成完整的 Markdown 架构报告
- 交互模式下用 Claude AI 问答代码
- 支持 Anthropic API 直连和 AWS Bedrock 双后端

## 2. 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python >= 3.11 |
| AST 分析 | `ast` (标准库) |
| 文件扫描 | `pathlib` (标准库) |
| CLI | `argparse` (标准库) |
| AI 对话 | `anthropic` SDK / `httpx` (Bedrock) |
| 数据建模 | `dataclasses` (标准库) |
| 测试 | `unittest` (标准库) |

## 3. 目录结构

```
claude-code-robin/
├── src/                                # 核心源码包 (5 个模块, ~434 行)
│   ├── __init__.py                     # 公开 API 导出
│   ├── main.py                         # CLI 入口 & 交互式 REPL & Claude AI 对话
│   ├── models.py                       # 核心数据模型 (5 个 dataclass)
│   ├── scanner.py                      # 文件系统扫描 & AST 依赖分析
│   └── reporter.py                     # Markdown 报告生成引擎
├── tests/
│   └── test_porting_workspace.py       # 12 个测试用例
├── pyproject.toml                      # 包配置 (pip install)
├── LICENSE                             # MIT 开源协议
├── README.md                           # 项目说明
└── ARCHITECTURE.md                     # 本文件
```

---

## 4. 核心模块详解

### 4.1 `models.py` — 核心数据模型（基础层）

项目最底层模块，零内部依赖。定义 5 个 dataclass，构成整个项目的类型基础。

#### `Module`（不可变）

描述扫描发现的一个 Python 模块：

```python
@dataclass(frozen=True)
class Module:
    name: str           # 模块名，如 "main.py" 或 "utils"（目录模块）
    path: str           # 完整路径
    file_count: int     # 该模块下的 .py 文件数量
    description: str = ''  # 可选的模块描述
```

**设计要点：**
- `frozen=True` 保证不可变，适合存入 tuple 安全传递
- `description` 默认空字符串，scanner 扫描时不填，用户可在 reporter 层扩展
- 对于单文件模块（如 `main.py`），`file_count = 1`；对于目录模块（如 `utils/`），`file_count` 为目录下 `.py` 文件总数

#### `Dependency`（不可变）

描述两个模块之间的 import 依赖关系：

```python
@dataclass(frozen=True)
class Dependency:
    source: str         # 发起 import 的模块名
    target: str         # 被 import 的模块/包名
    import_type: str = 'absolute'  # 'absolute' | 'relative' | 'third_party'
```

**import_type 分类规则：**
- `absolute` — `import os`、`from pathlib import Path`
- `relative` — `from .models import Module`（`node.level > 0`）
- `third_party` — 与 absolute 相同格式，后续可通过对比 stdlib 列表区分

**实例化示例：**
```python
Dependency(source='main', target='reporter', import_type='absolute')
Dependency(source='scanner', target='models', import_type='relative')
```

#### `ProjectStats`（不可变）

项目级统计信息：

```python
@dataclass(frozen=True)
class ProjectStats:
    total_files: int          # .py 文件总数
    total_lines: int          # 代码总行数
    total_modules: int        # 顶层模块数
    avg_lines_per_file: float # 平均每文件行数
```

#### `ProjectManifest` — 完整扫描结果

`scan_project()` 的返回类型，包含项目的所有元信息：

```python
@dataclass
class ProjectManifest:
    root: Path                              # 项目根目录
    total_python_files: int                 # .py 文件总数
    modules: tuple[Module, ...] = ()        # 发现的模块列表
    stats: ProjectStats | None = None       # 聚合统计信息

    def to_markdown(self) -> str:
        """渲染为 Markdown 格式的项目清单"""
```

**`to_markdown()` 输出示例：**
```markdown
## Project Manifest

Root: `/Users/xxx/my-project/src`
Total Python files: **5**
Total lines: **434**
Average lines per file: **86.8**

Modules:
- `scanner.py` (1 files)
- `models.py` (1 files)
- `reporter.py` (1 files)
- `main.py` (1 files)
```

#### `ArchReport` — 报告容器

组合多个报告段落，提供统一渲染：

```python
@dataclass
class ArchReport:
    title: str                                # 报告标题
    sections: list[str] = field(default_factory=list)  # Markdown 段落列表

    def render(self) -> str:
        """拼接标题和所有段落，用双换行分隔"""
        return '\n\n'.join([f'# {self.title}', *self.sections])
```

---

### 4.2 `scanner.py` — 文件系统扫描 & AST 依赖分析（核心引擎）

项目的核心功能模块，包含两个独立的分析函数。是唯一与文件系统和 AST 交互的模块。

#### `scan_project(root) → ProjectManifest`

**签名：** `def scan_project(root: Path | str) -> ProjectManifest`

**功能：** 扫描指定目录，统计所有 Python 文件，构建项目清单。

**执行流程（逐步）：**

```
1. root = Path(root).resolve()
   └── 转为绝对路径，支持传入 str 或 Path

2. if not root.is_dir(): raise ValueError
   └── 目录不存在时抛出明确错误（而非静默返回空结果）

3. files = [p for p in root.rglob('*.py') if p.is_file() and '__pycache__' not in p.parts]
   └── 递归扫描，排除 __pycache__ 目录

4. Counter 统计每个顶层模块的文件数
   ├── relative_to(root).parts 长度 > 1 → 取 parts[0]（目录名）
   └── 否则 → 取 rel.name（文件名）

5. 统计总行数
   └── 逐文件 read_text() + splitlines()，捕获 OSError/UnicodeDecodeError

6. 构建 ProjectStats
   └── avg_lines_per_file = total_lines / len(files)，空项目时为 0.0

7. 返回 ProjectManifest
   └── modules 按 counter.most_common() 降序排列
```

**文件归属判断示例：**
```python
# 单文件模块
# /project/src/main.py → relative = 'main.py' → parts = ('main.py',) → name = 'main.py'

# 目录模块
# /project/src/utils/helper.py → relative = 'utils/helper.py' → parts = ('utils', 'helper.py') → name = 'utils'
# /project/src/utils/parser.py → 同归属 'utils'，file_count = 2
```

**错误处理：**
- 目录不存在 → `ValueError`
- 单个文件读取失败 → 跳过该文件（`try/except`），不影响其余文件统计

#### `scan_dependencies(root) → list[Dependency]`

**签名：** `def scan_dependencies(root: Path | str) -> list[Dependency]`

**功能：** 使用 Python AST 模块解析所有 `.py` 文件的 import 语句，提取模块间依赖关系。

**执行流程：**

```
1. 收集所有 .py 文件（同 scan_project 的过滤规则）

2. 对每个文件：
   ├── ast.parse(source_text) 解析为语法树
   ├── 确定 source_name（同归属判断逻辑）
   └── ast.walk(tree) 遍历所有节点：
       │
       ├── ast.Import 节点（如 import os, json）
       │   └── 取 alias.name.split('.')[0] 作为 target
       │       例：import os.path → target = 'os'
       │
       └── ast.ImportFrom 节点（如 from .models import Module）
           ├── node.level > 0（相对导入）
           │   └── import_type = 'relative'
           │       target = node.module.split('.')[0] 或 '.'
           └── node.level == 0（绝对导入）
               └── import_type = 'absolute'
                   target = node.module.split('.')[0]

3. 返回所有 Dependency 列表
```

**AST 节点解析示例：**
```python
# 源代码：from .models import Module, Dependency
# AST 节点：ImportFrom(module='models', names=[...], level=1)
# 结果：Dependency(source='scanner', target='models', import_type='relative')

# 源代码：import ast
# AST 节点：Import(names=[alias(name='ast')])
# 结果：Dependency(source='scanner', target='ast', import_type='absolute')

# 源代码：from collections import Counter
# AST 节点：ImportFrom(module='collections', names=[...], level=0)
# 结果：Dependency(source='scanner', target='collections', import_type='absolute')
```

**错误处理：**
- 文件读取失败 → 跳过（`OSError`）
- 语法错误的 .py 文件 → 跳过（`SyntaxError`）
- 编码问题 → 跳过（`UnicodeDecodeError`）

---

### 4.3 `reporter.py` — 报告生成引擎（聚合层）

将 scanner 的原始数据转化为人类可读的 Markdown 报告。是 scanner 和 main 之间的桥梁。

#### `Reporter` 类

```python
class Reporter:
    def __init__(self, manifest: ProjectManifest, dependencies: list[Dependency] | None = None):
        self.manifest = manifest
        self.dependencies = dependencies or []
```

**构造方式：**

```python
# 方式 1：手动构造（适合测试或已有数据）
manifest = scan_project('./src')
deps = scan_dependencies('./src')
reporter = Reporter(manifest=manifest, dependencies=deps)

# 方式 2：工厂方法（一步到位，推荐）
reporter = Reporter.from_path('./src')  # 内部自动调用 scan_project + scan_dependencies
```

#### `render_manifest() → str`

渲染项目清单，直接委托给 `ProjectManifest.to_markdown()`。

#### `render_stats() → str`

渲染统计表格：

```markdown
## Project Statistics

| Metric | Value |
|--------|-------|
| Total Python files | 5 |
| Total lines of code | 434 |
| Total modules | 5 |
| Avg lines per file | 86.8 |
```

#### `render_dependencies() → str`

将扁平的 `list[Dependency]` 按 source 分组，渲染为结构化的依赖文档：

```markdown
## Module Dependencies

### `main`
- argparse (absolute)
- os (absolute)
- reporter (relative)
- scanner (relative)
- shlex (absolute)

### `scanner`
- ast (absolute)
- collections (absolute)
- models (relative)
- pathlib (absolute)
```

**内部逻辑：**
1. 按 `dep.source` 分组到 `dict[str, list[str]]`
2. 每组内去重并排序
3. 渲染为三级标题 + 列表

#### `render_full_report() → str`

组合所有子报告，通过 `ArchReport` 容器统一渲染：

```python
def render_full_report(self) -> str:
    report = ArchReport(
        title='Architecture Report',
        sections=[
            self.render_manifest(),       # 项目清单
            self.render_stats(),          # 统计信息
            self.render_dependencies(),   # 依赖分析
        ],
    )
    return report.render()  # 用 '\n\n' 拼接所有段落
```

---

### 4.4 `main.py` — CLI 入口（应用层）

项目的顶层入口，包含 CLI 解析、命令路由、交互式 REPL 和 Claude AI 对话四大功能块。

#### 4.4.1 CLI 命令体系

```
claude-code-robin <command> [options]
  ├── scan [path]            扫描项目，打印清单
  ├── arch [path] [-o file]  生成完整架构报告（可输出到文件）
  ├── deps [path]            分析并打印模块依赖
  ├── stats [path]           打印项目统计
  └── interactive            启动交互式 REPL
```

所有命令的 `path` 参数默认为当前目录 `.`。

#### 4.4.2 双路由机制

| 函数 | 场景 | 输入 | 特点 |
|------|------|------|------|
| `main(argv)` | CLI 直接调用 | argparse 解析后的 args | 类型安全，返回退出码 |
| `run_command(cmd)` | 交互模式内部 | 原始字符串 | shlex.split() 手动解析，宽容处理未知命令 |

`main()` 额外支持 `--output` 参数将报告写入文件（`arch` 命令）：
```python
if args.output:
    Path(args.output).write_text(output, encoding='utf-8')
```

#### 4.4.3 Claude AI 双后端架构

```
chat(user_input, history)
  │
  ├─ 检测环境变量
  │   ├── CLAUDE_CODE_USE_BEDROCK=1 且 AWS_BEARER_TOKEN_BEDROCK 非空
  │   │    → _chat_bedrock()  [httpx.post → Bedrock REST API]
  │   │
  │   └── 否则
  │        → _chat_anthropic()  [anthropic SDK → Messages API]
  │
  └─ 异常处理
      ├── 成功：追加 assistant 消息到 history，打印回复
      └── 失败：print 错误，pop 回滚 user 消息，返回原 history
```

**System Prompt：**
```
You are Robin, an expert Python code architecture analyst.
Help users understand their codebase structure, dependencies, and design patterns.
Answer concisely.
```

**对话历史管理：**
- `history: list[dict]` 在会话级维护，退出即丢失
- 每轮追加 `{'role': 'user', ...}` + `{'role': 'assistant', ...}`
- API 失败时 `history.pop()` 撤销用户消息，避免孤立消息导致后续 API 报错

#### 4.4.4 交互式 REPL

```python
robin> scan ./src         # 首个单词在 COMMANDS 集合中 → 本地执行
robin> 分析一下设计模式     # 首个单词不在 COMMANDS 中 → 发给 Claude AI
robin> exit               # 退出（也支持 quit、Ctrl+C、Ctrl+D）
```

**COMMANDS 集合：** `{'scan', 'arch', 'deps', 'stats', 'help'}`

---

### 4.5 `__init__.py` — 包导出（API 层）

通过 `__all__` 定义公开 API：

```python
__all__ = [
    'ArchReport', 'Dependency', 'Module',     # 数据模型
    'ProjectManifest', 'ProjectStats',         # 数据模型
    'Reporter',                                 # 报告引擎
    'scan_dependencies', 'scan_project',        # 扫描函数
]
```

---

## 5. 核心数据流

```
         用户指定的 Python 项目目录
                    │
                    ▼
   ┌─────────────────────────────────┐
   │         scanner.py              │
   │                                 │
   │  scan_project(root)             │
   │    ├── rglob('*.py')            │
   │    ├── Counter 统计模块          │
   │    ├── 逐文件统计行数            │
   │    └── → ProjectManifest        │
   │                                 │
   │  scan_dependencies(root)        │
   │    ├── ast.parse() 逐文件       │
   │    ├── ast.walk() 提取 import   │
   │    └── → list[Dependency]       │
   └──────────────┬──────────────────┘
                  │
                  ▼
   ┌─────────────────────────────────┐
   │         reporter.py             │
   │                                 │
   │  Reporter(manifest, deps)       │
   │    ├── render_manifest()        │
   │    ├── render_stats()           │
   │    ├── render_dependencies()    │
   │    └── render_full_report()     │
   │         └── ArchReport.render() │
   └──────────────┬──────────────────┘
                  │
                  ▼
   ┌─────────────────────────────────┐
   │          main.py                │
   │                                 │
   │  CLI 模式:                      │
   │    scan/arch/deps/stats → stdout│
   │    arch -o file → 写入文件       │
   │                                 │
   │  交互模式:                      │
   │    已知命令 → 本地执行            │
   │    其他输入 → Claude AI 对话     │
   └─────────────────────────────────┘
```

## 6. 测试体系

12 个测试用例，覆盖 4 个层级：

| 测试类 | 测试数 | 覆盖内容 |
|--------|--------|----------|
| `ScannerTests` | 4 | 文件扫描、统计信息、错误处理、依赖分析 |
| `ReporterTests` | 3 | 完整报告、清单渲染、统计渲染 |
| `ModelTests` | 2 | Module 创建、Manifest Markdown 渲染 |
| `CLITests` | 3 | scan/arch/stats 命令端到端 |

**测试覆盖层级：**
```
CLITests (集成) → main() → Reporter → scanner → models
ReporterTests    → Reporter → scanner → models
ScannerTests     → scanner → models
ModelTests       → models
```

运行：
```bash
python3 -m unittest discover -s tests -v

# 预期输出
# test_cli_arch_runs ... ok
# test_cli_scan_runs ... ok
# test_cli_stats_runs ... ok
# ...
# Ran 12 tests in 0.XXXs
# OK
```

## 7. 模块依赖关系

```
┌─────────────────────────────────────────┐
│               main.py                    │
│     (CLI + REPL + Claude AI 对话)        │
│   [argparse, os, shlex, anthropic, httpx]│
└──────────────────┬──────────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │   reporter.py     │
         │  (报告生成引擎)    │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │   scanner.py      │
         │  (扫描 & AST)     │
         │  [ast, Counter,   │
         │   pathlib]        │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │   models.py       │
         │  (数据模型)       │
         │  [dataclasses]    │
         └──────────────────┘
```

**线性依赖链，无循环依赖。** 每一层只依赖下一层。

## 8. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥（直连模式必须） | — |
| `CLAUDE_CODE_USE_BEDROCK` | 设为 `1` 使用 AWS Bedrock | 不启用 |
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock 认证 Token | — |
| `AWS_REGION` | AWS 区域 | `us-east-1` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Bedrock 模型 ID | `us.anthropic.claude-sonnet-4-6` |

## 9. 扩展指南

### 新增 CLI 命令

以新增 `tree` 命令为例：

```python
# 1. build_parser() 中添加
tree_parser = subparsers.add_parser('tree', help='print directory tree')
tree_parser.add_argument('path', nargs='?', default='.')

# 2. main() 中添加
if args.command == 'tree':
    # 实现逻辑
    return 0

# 3. COMMANDS 集合中添加（支持交互模式）
COMMANDS = {'scan', 'arch', 'deps', 'stats', 'help', 'tree'}

# 4. run_command() 中添加分支
elif command == 'tree':
    # 实现逻辑
```

### 新增报告段落

在 `Reporter` 中添加 `render_xxx()` 方法，然后在 `render_full_report()` 的 `sections` 列表中引用。

### 新增数据模型

在 `models.py` 中定义新 dataclass，在 `__init__.py` 的 `__all__` 中导出。

### 新增 AI 后端

在 `main.py` 中添加 `_chat_xxx()` 函数，在 `chat()` 的环境变量检测逻辑中增加分支。
