from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from src.scanner import scan_project, scan_dependencies
from src.reporter import Reporter
from src.models import Module, ProjectManifest, ProjectStats

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ScannerTests(unittest.TestCase):
    def test_scan_finds_python_files(self) -> None:
        manifest = scan_project(PROJECT_ROOT / 'src')
        self.assertGreaterEqual(manifest.total_python_files, 4)
        self.assertTrue(manifest.modules)

    def test_scan_includes_stats(self) -> None:
        manifest = scan_project(PROJECT_ROOT / 'src')
        self.assertIsNotNone(manifest.stats)
        self.assertGreater(manifest.stats.total_lines, 0)
        self.assertGreater(manifest.stats.avg_lines_per_file, 0)

    def test_scan_nonexistent_dir_raises(self) -> None:
        with self.assertRaises(ValueError):
            scan_project('/nonexistent/path/that/does/not/exist')

    def test_scan_dependencies_returns_list(self) -> None:
        deps = scan_dependencies(PROJECT_ROOT / 'src')
        self.assertIsInstance(deps, list)
        self.assertTrue(len(deps) > 0)


class ReporterTests(unittest.TestCase):
    def test_full_report_contains_sections(self) -> None:
        reporter = Reporter.from_path(PROJECT_ROOT / 'src')
        report = reporter.render_full_report()
        self.assertIn('Architecture Report', report)
        self.assertIn('Project Manifest', report)
        self.assertIn('Project Statistics', report)
        self.assertIn('Module Dependencies', report)

    def test_manifest_markdown(self) -> None:
        reporter = Reporter.from_path(PROJECT_ROOT / 'src')
        md = reporter.render_manifest()
        self.assertIn('Total Python files', md)
        self.assertIn('Modules:', md)

    def test_stats_markdown(self) -> None:
        reporter = Reporter.from_path(PROJECT_ROOT / 'src')
        md = reporter.render_stats()
        self.assertIn('Total Python files', md)
        self.assertIn('Total lines of code', md)


class ModelTests(unittest.TestCase):
    def test_module_creation(self) -> None:
        mod = Module(name='test', path='/test', file_count=1, description='a test module')
        self.assertEqual(mod.name, 'test')
        self.assertEqual(mod.description, 'a test module')

    def test_manifest_to_markdown(self) -> None:
        manifest = ProjectManifest(
            root=Path('/tmp/test'),
            total_python_files=3,
            modules=(Module(name='app.py', path='/tmp/test/app.py', file_count=1, description='main app'),),
            stats=ProjectStats(total_files=3, total_lines=100, total_modules=1, avg_lines_per_file=33.3),
        )
        md = manifest.to_markdown()
        self.assertIn('Total Python files: **3**', md)
        self.assertIn('`app.py`', md)
        self.assertIn('Total lines: **100**', md)


class CLITests(unittest.TestCase):
    def test_cli_scan_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'scan', str(PROJECT_ROOT / 'src')],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Project Manifest', result.stdout)

    def test_cli_arch_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'arch', str(PROJECT_ROOT / 'src')],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Architecture Report', result.stdout)

    def test_cli_stats_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'stats', str(PROJECT_ROOT / 'src')],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Total Python files', result.stdout)


if __name__ == '__main__':
    unittest.main()
