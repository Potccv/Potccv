"""Run synthetic-fixture tests in an explicitly supplied workspace scratch path."""

import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

from rulecheck.paths import is_redirect


def validate_scratch(workspace: Path, scratch: Path) -> Path:
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ValueError("--workspace 必须是已存在工作区的完整路径。")
    if not scratch.is_absolute() or not scratch.is_dir():
        raise ValueError("--scratch 必须是已存在目录的完整路径。")
    for candidate in (scratch, *scratch.parents):
        if is_redirect(candidate) or os.path.lexists(candidate / ".git"):
            raise ValueError("测试目录不能包含路径重定向，也不能位于 Git 仓库内。")
    workspace = workspace.resolve()
    scratch = scratch.resolve()
    batches = workspace / "tmp" / "rule-check"
    if not scratch.is_relative_to(batches) or scratch == batches:
        raise ValueError("测试目录必须位于 <工作区>/tmp/rule-check/<批次>/。")
    return scratch


def main() -> int:
    parser = argparse.ArgumentParser(description="使用指定工作区临时目录运行合成案例测试。")
    parser.add_argument("--workspace", required=True, type=Path, help="工作区根目录的完整路径")
    parser.add_argument("--scratch", required=True, type=Path, help="已存在的工作区 tmp/<任务>/<批次> 完整路径")
    args = parser.parse_args()
    try:
        scratch = validate_scratch(args.workspace, args.scratch)
    except ValueError as error:
        parser.error(str(error))
    os.environ["RULE_CHECK_TEST_TMP"] = str(scratch)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(scratch)
    tempfile.tempdir = str(scratch)
    tool_root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(tool_root / "tests"), top_level_dir=str(tool_root))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
