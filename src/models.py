from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Module:
    """Represents a discovered Python module in the scanned project."""
    name: str
    path: str
    file_count: int
    description: str = ''


@dataclass(frozen=True)
class Dependency:
    """Represents an import dependency between two modules."""
    source: str
    target: str
    import_type: str = 'absolute'  # 'absolute' | 'relative' | 'third_party'


@dataclass(frozen=True)
class ProjectStats:
    """Aggregate statistics for a scanned project."""
    total_files: int
    total_lines: int
    total_modules: int
    avg_lines_per_file: float


@dataclass
class ProjectManifest:
    """Complete manifest of a scanned Python project."""
    root: Path
    total_python_files: int
    modules: tuple[Module, ...] = ()
    stats: ProjectStats | None = None

    def to_markdown(self) -> str:
        lines = [
            f'## Project Manifest',
            '',
            f'Root: `{self.root}`',
            f'Total Python files: **{self.total_python_files}**',
        ]
        if self.stats:
            lines.extend([
                f'Total lines: **{self.stats.total_lines}**',
                f'Average lines per file: **{self.stats.avg_lines_per_file:.1f}**',
            ])
        lines.extend(['', 'Modules:'])
        for mod in self.modules:
            desc = f' — {mod.description}' if mod.description else ''
            lines.append(f'- `{mod.name}` ({mod.file_count} files){desc}')
        return '\n'.join(lines)


@dataclass
class ArchReport:
    """A generated architecture report with sections."""
    title: str
    sections: list[str] = field(default_factory=list)

    def render(self) -> str:
        return '\n\n'.join([f'# {self.title}', *self.sections])
