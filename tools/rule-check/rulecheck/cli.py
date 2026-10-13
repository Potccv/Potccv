"""Command routing and stdout reports; no repair or output-file side effects."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .models import CheckResult


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="只读检查约束仓库或工作区事项。")
    root.add_argument("--version", action="version", version=__version__)
    modes = root.add_subparsers(dest="mode", required=True)
    rules = modes.add_parser("rules", help="检查被 Git 跟踪的规则与公开示例")
    rules.add_argument("repo", type=Path, help="约束 Git 仓库根目录")
    tasks = modes.add_parser("tasks", help="检查源码仓库之外的工作区事项")
    tasks.add_argument("--workspace", type=Path, required=True, help="工作区根目录")
    tasks.add_argument(
        "--source-repo", type=Path, action="append", required=True,
        help="源码仓库根目录；多个仓库分别重复指定",
    )
    tasks.add_argument(
        "--tasks-dir", type=Path,
        help="工作区内事项目录的完整路径，默认 <工作区>/docs/tasks",
    )
    for mode in (rules, tasks):
        mode.add_argument("--format", choices=("text", "json"), default="text")
    return root


def report(result: CheckResult, mode: str, targets: dict, output_format: str) -> None:
    payload = {
        "schema_version": 1,
        "tool_version": __version__,
        "mode": mode,
        "targets": targets,
        "ok": result.ok,
        "stats": result.stats,
        "issues": [issue.to_dict() for issue in result.issues],
    }
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"{'通过' if result.ok else '未通过'}：{mode}")
    if result.stats:
        print("统计：" + ", ".join(f"{key}={value}" for key, value in sorted(result.stats.items())))
    for issue in result.issues:
        location = issue.path
        if location and issue.line is not None:
            location += f":{issue.line}"
        print(f"[{issue.severity}] {issue.code} {location}: {issue.message}")


def main(argv: list[str] | None = None) -> int:
    # Keep Chinese reports consistent under Windows shells and redirected output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    if args.mode == "rules":
        targets = {"repository": str(args.repo.absolute())}
    else:
        targets = {
            "workspace": str(args.workspace.absolute()),
            "source_repositories": [str(path.absolute()) for path in args.source_repo],
            "tasks_directory": str((args.tasks_dir or args.workspace / "docs" / "tasks").absolute()),
        }
    exit_code = None
    try:
        if args.mode == "rules":
            from .repository import check_repository

            result = check_repository(args.repo)
        else:
            from .tasks import check_tasks

            result = check_tasks(args.workspace, args.source_repo, args.tasks_dir)
    except ModuleNotFoundError:
        result = CheckResult()
        result.add("DEPENDENCY_MISSING", "缺少运行依赖；请按工具 README 在独立环境安装 requirements.txt。")
        exit_code = 2
    except (OSError, UnicodeError, ValueError) as error:
        result = CheckResult()
        # Do not echo exception strings that might contain a parsed private value.
        result.add("CHECK_FAILED", f"无法完成检查（{type(error).__name__}），请确认目标路径、权限和文件编码。")
        exit_code = 2
    report(result, args.mode, targets, args.format)
    return exit_code if exit_code is not None else (0 if result.ok else 1)
