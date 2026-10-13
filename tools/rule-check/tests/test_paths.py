"""Boundary regressions for shared path helpers and fixture placement."""

from pathlib import Path
import unittest

from rulecheck.paths import contains_redirect
from run_tests import validate_scratch
from tests.support import temporary_directory


class PathChecks(unittest.TestCase):
    def test_parent_segments_never_pass_lexical_redirect_check(self):
        with temporary_directory() as folder:
            root = Path(folder) / "trusted"
            root.mkdir()
            self.assertTrue(contains_redirect(root / ".." / "outside.md", root))
            self.assertFalse(contains_redirect(root / "ordinary.md", root))
            self.assertFalse(contains_redirect(root / "child" / ".." / "ordinary.md", root))

    def test_runner_accepts_only_workspace_batch_directories(self):
        with temporary_directory() as folder:
            workspace = Path(folder)
            batch = workspace / "tmp" / "rule-check" / "batch"
            batch.mkdir(parents=True)
            self.assertEqual(validate_scratch(workspace, batch), batch.resolve())
            for rejected in (workspace, batch.parent, workspace / "tmp"):
                with self.subTest(path=rejected), self.assertRaises(ValueError):
                    validate_scratch(workspace, rejected)

    def test_runner_refuses_nested_repository_before_tests(self):
        with temporary_directory() as folder:
            workspace = Path(folder)
            batch = workspace / "tmp" / "rule-check" / "batch"
            batch.mkdir(parents=True)
            (workspace / "tmp" / ".git").write_text("gitdir: synthetic", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_scratch(workspace, batch)
