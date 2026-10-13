"""Test fixtures are only created inside the explicitly supplied scratch root."""

import os
from pathlib import Path
import tempfile


def temporary_directory(prefix: str = "rule-check-") -> tempfile.TemporaryDirectory:
    configured = os.environ.get("RULE_CHECK_TEST_TMP")
    if not configured:
        raise RuntimeError("Use run_tests.py --scratch with a workspace test directory.")
    scratch = Path(configured).resolve()
    if not scratch.is_dir():
        raise RuntimeError("The configured test scratch directory does not exist.")
    return tempfile.TemporaryDirectory(prefix=prefix, dir=scratch)
