# claude-code-robin Architecture

## Quick Start

```bash
# Install
pip install -e .

# Scan a project
claude-code-robin scan ./src

# Full architecture report
claude-code-robin arch ./src -o ARCHITECTURE.md

# Run tests
python3 -m unittest discover -s tests -v
```

## Module Overview

### `models.py` — Core Data Models

All shared data structures. Zero external dependencies.

| Class | Description |
|-------|-------------|
| `Module` | A discovered Python module (name, path, file_count, description) |
| `Dependency` | An import relationship (source → target, import_type) |
| `ProjectStats` | Aggregate stats (total_files, total_lines, avg_lines_per_file) |
| `ProjectManifest` | Complete scan result with modules and stats, has `to_markdown()` |
| `ArchReport` | Report container with title + sections, has `render()` |

### `scanner.py` — Filesystem & AST Analysis

Two core functions:

**`scan_project(root) → ProjectManifest`**
1. `rglob('*.py')` to find all Python files (excluding `__pycache__`)
2. `Counter` to group files by top-level module
3. Count total lines across all files
4. Build `ProjectStats` and `ProjectManifest`

**`scan_dependencies(root) → list[Dependency]`**
1. Parse each `.py` file with `ast.parse()`
2. Walk AST nodes for `Import` and `ImportFrom`
3. Classify as `absolute`, `relative`, or `third_party`
4. Return list of `Dependency` objects

### `reporter.py` — Report Generation

**`Reporter`** orchestrates scanner output into Markdown reports:

- `from_path(path)` — factory that scans + analyzes in one step
- `render_manifest()` — project structure overview
- `render_dependencies()` — module dependency breakdown
- `render_stats()` — statistics table
- `render_full_report()` — all sections combined

### `main.py` — CLI & Interactive Shell

Four CLI commands + interactive REPL + Claude AI chat:

| Command | Description |
|---------|-------------|
| `scan [path]` | Print project manifest |
| `arch [path] [-o file]` | Generate full architecture report |
| `deps [path]` | Print dependency analysis |
| `stats [path]` | Print project statistics |
| `interactive` | REPL with Claude conversation fallback |

AI chat supports dual backends (Anthropic API direct / AWS Bedrock).

## Data Flow

```
Filesystem (*.py files)
       │
       ▼
   scanner.py
   ├── scan_project()      → ProjectManifest
   └── scan_dependencies() → list[Dependency]
       │
       ▼
   reporter.py
   └── Reporter.render_full_report() → Markdown string
       │
       ▼
   main.py
   ├── CLI stdout
   ├── File output (-o)
   └── Interactive REPL
```

## Dependency Graph

```
main.py
  └── reporter.py
        └── scanner.py
              └── models.py (no internal deps)
```

Linear dependency chain. No circular imports.
