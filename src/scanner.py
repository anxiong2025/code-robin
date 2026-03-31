from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from .models import Dependency, Module, ProjectManifest, ProjectStats


def scan_project(root: Path | str) -> ProjectManifest:
    """Scan a Python project directory and build a manifest."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f'Not a directory: {root}')

    files = [p for p in root.rglob('*.py') if p.is_file() and '__pycache__' not in p.parts]

    # Count files per top-level module
    counter: Counter[str] = Counter()
    for path in files:
        rel = path.relative_to(root)
        key = rel.parts[0] if len(rel.parts) > 1 else rel.name
        counter[key] = counter.get(key, 0) + 1

    # Count total lines
    total_lines = 0
    for path in files:
        try:
            total_lines += len(path.read_text(encoding='utf-8').splitlines())
        except (OSError, UnicodeDecodeError):
            pass

    modules = tuple(
        Module(name=name, path=str(root / name), file_count=count)
        for name, count in counter.most_common()
    )

    avg = total_lines / len(files) if files else 0.0
    stats = ProjectStats(
        total_files=len(files),
        total_lines=total_lines,
        total_modules=len(modules),
        avg_lines_per_file=round(avg, 1),
    )

    return ProjectManifest(
        root=root,
        total_python_files=len(files),
        modules=modules,
        stats=stats,
    )


def scan_dependencies(root: Path | str) -> list[Dependency]:
    """Analyze import statements across all Python files to extract dependencies."""
    root = Path(root).resolve()
    files = [p for p in root.rglob('*.py') if p.is_file() and '__pycache__' not in p.parts]
    deps: list[Dependency] = []

    for path in files:
        try:
            source_text = path.read_text(encoding='utf-8')
            tree = ast.parse(source_text, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        source_name = path.relative_to(root).parts[0] if len(path.relative_to(root).parts) > 1 else path.stem

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name.split('.')[0]
                    deps.append(Dependency(source=source_name, target=target, import_type='absolute'))
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    # Relative import
                    target = node.module.split('.')[0] if node.module else '.'
                    deps.append(Dependency(source=source_name, target=target, import_type='relative'))
                elif node.module:
                    target = node.module.split('.')[0]
                    deps.append(Dependency(source=source_name, target=target, import_type='absolute'))

    return deps
