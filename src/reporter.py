from __future__ import annotations

from pathlib import Path

from .models import ArchReport, Dependency, ProjectManifest
from .scanner import scan_dependencies, scan_project


class Reporter:
    """Generates architecture reports from project analysis."""

    def __init__(self, manifest: ProjectManifest, dependencies: list[Dependency] | None = None):
        self.manifest = manifest
        self.dependencies = dependencies or []

    @classmethod
    def from_path(cls, path: Path | str) -> Reporter:
        """Scan a project and create a reporter in one step."""
        root = Path(path).resolve()
        manifest = scan_project(root)
        deps = scan_dependencies(root)
        return cls(manifest=manifest, dependencies=deps)

    def render_manifest(self) -> str:
        """Render the project manifest as Markdown."""
        return self.manifest.to_markdown()

    def render_dependencies(self) -> str:
        """Render dependency analysis as Markdown."""
        if not self.dependencies:
            return '_No dependencies found._'

        # Group by source
        dep_map: dict[str, list[str]] = {}
        for dep in self.dependencies:
            dep_map.setdefault(dep.source, []).append(f'{dep.target} ({dep.import_type})')

        lines = ['## Module Dependencies', '']
        for source, targets in sorted(dep_map.items()):
            unique_targets = sorted(set(targets))
            lines.append(f'### `{source}`')
            for t in unique_targets:
                lines.append(f'- {t}')
            lines.append('')
        return '\n'.join(lines)

    def render_stats(self) -> str:
        """Render project statistics as Markdown."""
        stats = self.manifest.stats
        if not stats:
            return '_No statistics available._'
        lines = [
            '## Project Statistics',
            '',
            f'| Metric | Value |',
            f'|--------|-------|',
            f'| Total Python files | {stats.total_files} |',
            f'| Total lines of code | {stats.total_lines} |',
            f'| Total modules | {stats.total_modules} |',
            f'| Avg lines per file | {stats.avg_lines_per_file} |',
        ]
        return '\n'.join(lines)

    def render_full_report(self) -> str:
        """Generate a complete architecture report."""
        report = ArchReport(
            title='Architecture Report',
            sections=[
                self.render_manifest(),
                self.render_stats(),
                self.render_dependencies(),
            ],
        )
        return report.render()
