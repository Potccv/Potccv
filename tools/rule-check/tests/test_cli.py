"""Exercise public commands and verify the target tree stays unchanged."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.support import temporary_directory


TOOL = Path(__file__).resolve().parents[1] / "rule_check.py"
VALID_TASK = """# 独立校验工具

状态：todo
摘要：验证事项检查命令保持只读。

## 目标
确认命令行检查只读。

## 变更边界
仅包含合成事项的只读检查。

## 拆分依据
可独立验收：是；可独立迁移：是；失败时其他事项仍有价值：是。

## 工作清单
- [ ] 核验输入文件摘要。

## 验收条件
命令运行前后的目录、文件和内容一致。

## 当前进展与接续
使用合成事项验证。

## 关联资料
无外部依赖。

---
创建时间：2026-10-13 20:00:00
最后更新时间：2026-10-13 20:01:00
"""


def snapshot(root: Path) -> dict:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        for path in root.rglob("*")
    }


class CliTests(unittest.TestCase):
    def invoke(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        # A fresh ordinary interpreter must rely on the launcher itself to avoid
        # writing bytecode; the test runner's environment must not conceal bugs.
        environment = {
            key: value for key, value in os.environ.items()
            if key.upper() not in {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"}
        }
        tool_before = snapshot(TOOL.parent)
        fixture_before = snapshot(cwd) if cwd is not None else None
        completed = subprocess.run(
            [sys.executable, str(TOOL), *args], capture_output=True,
            text=True, encoding="utf-8", timeout=30, env=environment,
            cwd=cwd if cwd is not None else TOOL.parent,
        )
        self.assertEqual(snapshot(TOOL.parent), tool_before,
                         "CLI must not add bytecode, logs or other tool-tree files")
        if cwd is not None:
            self.assertEqual(snapshot(cwd), fixture_before,
                             "CLI must not add or modify fixture files or directories")
        return completed

    def task_for_state(self, state: str) -> str:
        text = VALID_TASK
        if state == "done":
            text = text.replace("状态：todo", "状态：done").replace("最后更新时间：2026-10-13 20:01:00", "最后更新时间：2026-10-13 20:02:00")
            text += "完成时间：2026-10-13 20:02:00\n"
        elif state == "drop":
            text = text.replace("状态：todo", "状态：drop").replace("最后更新时间：2026-10-13 20:01:00", "最后更新时间：2026-10-13 20:02:00")
            text = text.replace("状态：drop\n", "状态：drop\n终止原因：合成回归已取消\n")
            text += "终止时间：2026-10-13 20:02:00\n"
        return text

    def test_tasks_json_is_read_only(self):
        with temporary_directory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            pending = root / "docs" / "tasks" / "todo"
            pending.mkdir(parents=True)
            (pending / "T001-独立校验工具.md").write_text(self.task_for_state("todo"), encoding="utf-8")
            before = snapshot(root)
            completed = self.invoke("tasks", "--workspace", str(root), "--source-repo", str(source), "--format", "json", cwd=root)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["mode"], "tasks")
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(snapshot(root), before)

    def test_source_docs_target_fails_without_modification(self):
        with temporary_directory() as folder:
            root = Path(folder)
            source = root / "source"
            target = source / "docs" / "tasks"
            target.mkdir(parents=True)
            (target / "private.md").write_text("must not be read", encoding="utf-8")
            before = snapshot(root)
            completed = self.invoke("tasks", "--workspace", str(root), "--source-repo", str(source), "--tasks-dir", str(target), "--format", "json", cwd=root)
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertFalse(json.loads(completed.stdout)["ok"])
            self.assertNotIn("must not be read", completed.stdout)
            self.assertEqual(snapshot(root), before)

    def test_missing_source_argument_is_usage_error(self):
        completed = self.invoke("tasks", "--workspace", str(TOOL.parent))
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--source-repo", completed.stderr)

    def test_missing_repo_reports_failure_as_json(self):
        with temporary_directory() as folder:
            completed = self.invoke("rules", str(Path(folder) / "missing"), "--format", "json", cwd=Path(folder))
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(json.loads(completed.stdout)["ok"])

    def test_missing_default_task_directory_is_explicitly_skipped_without_creation(self):
        with temporary_directory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            completed = self.invoke("tasks", "--workspace", str(root),
                                    "--source-repo", str(source), "--format", "json", cwd=root)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("跳过", completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["stats"]["task_files"], 0)
            self.assertEqual(payload["stats"]["task_directories_skipped"], 1)
            issue = next(issue for issue in payload["issues"] if issue["code"] == "tasks.directory_absent")
            self.assertEqual(issue["severity"], "info")
            self.assertFalse((root / "docs").exists())

    def test_missing_explicit_task_directory_fails_without_creation(self):
        with temporary_directory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            target = root / "docs" / "custom-tasks"
            completed = self.invoke("tasks", "--workspace", str(root),
                                    "--source-repo", str(source), "--tasks-dir", str(target),
                                    "--format", "json", cwd=root)
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("tasks.directory_missing", {issue["code"] for issue in payload["issues"]})
            self.assertFalse((root / "docs").exists())

    def test_single_task_state_directory_does_not_create_other_states(self):
        for state in ("todo", "done", "drop"):
            with self.subTest(state=state), temporary_directory() as folder:
                root = Path(folder)
                source = root / "source"
                source.mkdir()
                target = root / "docs" / "tasks"
                state_directory = target / state
                state_directory.mkdir(parents=True)
                (state_directory / "T001-独立校验工具.md").write_text(self.task_for_state(state), encoding="utf-8")
                completed = self.invoke("tasks", "--workspace", str(root),
                                        "--source-repo", str(source), "--format", "json", cwd=root)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["stats"]["task_files"], 1)
                for other in {"todo", "done", "drop"} - {state}:
                    self.assertFalse((target / other).exists())

    def test_legacy_or_wrong_case_state_directories_are_rejected_without_reading_body(self):
        for state in ("待办事项", "Todo", "TODO", "Done", "DONE", "Drop", "DROP"):
            with self.subTest(state=state), temporary_directory() as folder:
                root = Path(folder)
                source = root / "source"
                source.mkdir()
                state_directory = root / "docs" / "tasks" / state
                state_directory.mkdir(parents=True)
                (state_directory / "T001-invalid.md").write_text("private body sentinel", encoding="utf-8")
                completed = self.invoke("tasks", "--workspace", str(root),
                                        "--source-repo", str(source), "--format", "json", cwd=root)
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertFalse(payload["ok"])
                self.assertIn("tasks.state_name", {issue["code"] for issue in payload["issues"]})
                self.assertNotIn("private body sentinel", completed.stdout)
