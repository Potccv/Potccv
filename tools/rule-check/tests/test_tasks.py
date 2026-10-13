"""Synthetic fixtures for strict todo/done/drop task records."""

from pathlib import Path
import unittest
from unittest.mock import patch

from rulecheck.tasks import check_tasks
from tests.support import temporary_directory


def task_text(status="todo", creation="2026-10-01 12:00:00", update="2026-10-02 12:00:00", *, completion=None, termination=None, reason=None, extra=""):
    text = (
        "# 独立事项\n\n状态：" + status + "\n\n"
        "## 目标\n预期结果。\n\n## 变更边界\n仅包含本事项结果。\n\n"
        "## 拆分依据\n可独立验收：是；可独立迁移：是；失败时其他事项仍有价值：是。\n\n"
        "## 工作清单\n- [ ] 实施步骤。\n\n"
        "## 验收条件\n可核验标准。\n\n## 当前进展与接续\n当前进展。\n\n"
        "## 关联资料\n相关资料。\n\n"
    )
    if reason is not None:
        text += f"终止原因：{reason}\n\n"
    text += "---\n创建时间：" + creation + "\n最后更新时间：" + update + "\n"
    if completion is not None:
        text += f"完成时间：{completion}\n"
    if termination is not None:
        text += f"终止时间：{termination}\n"
    return text + extra


class TaskChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory("tasks-")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.source = self.workspace / "project"
        self.source.mkdir()
        self.target = self.workspace / "docs" / "tasks"
        self.todo = self.target / "todo"
        self.done = self.target / "done"
        self.drop = self.target / "drop"
        for directory in (self.todo, self.done, self.drop):
            directory.mkdir(parents=True)

    def write(self, directory, name="T001-独立事项.md", text=None):
        path = directory / name
        path.write_text(task_text() if text is None else text, encoding="utf-8")
        return path

    def check(self, target=None, sources=None):
        return check_tasks(self.workspace, [self.source] if sources is None else sources, target)

    @staticmethod
    def codes(result):
        return {issue.code for issue in result.issues}

    def snapshot(self):
        return sorted((str(p.relative_to(self.workspace)), p.is_dir(), p.read_bytes() if p.is_file() else None) for p in self.workspace.rglob("*"))

    def test_valid_todo_done_drop(self):
        self.write(self.todo, text=task_text("todo"))
        self.write(self.done, "T002-已完成.md", task_text("done", completion="2026-10-02 12:00:00"))
        self.write(self.drop, "T003-已终止.md", task_text("drop", termination="2026-10-02 12:00:00", reason="范围取消"))
        result = self.check()
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.stats["task_files"], 3)

    def test_drop_requires_reason(self):
        self.write(self.drop, text=task_text("drop", termination="2026-10-02 12:00:00"))
        self.assertTrue({"tasks.termination_reason"} <= self.codes(self.check()))

    def test_drop_requires_terminal_footer(self):
        # Keep the reason valid so this assertion isolates footer placement.
        self.write(self.drop, "T002-后续.md", task_text("drop", reason="原因") + "终止时间：2026-10-02 12:00:00\n后续内容\n")
        self.assertIn("tasks.time_footer", self.codes(self.check()))

    def test_drop_rejects_completion_and_terminal_after_update(self):
        self.write(self.drop, text=task_text("drop", completion="2026-10-02 12:00:00", termination="2026-10-03 12:00:00", reason="原因"))
        codes = self.codes(self.check())
        self.assertTrue({"tasks.forbidden_time", "tasks.time_order"} <= codes)

    def test_todo_rejects_completion_or_termination(self):
        self.write(self.todo, text=task_text("todo", completion="2026-10-02 12:00:00", termination="2026-10-02 12:00:00"))
        self.assertIn("tasks.forbidden_time", self.codes(self.check()))

    def test_status_must_match_directory_exactly(self):
        self.write(self.todo, text=task_text("进行中"))
        self.write(self.done, "T002-错误.md", task_text("DONE", completion="2026-10-02 12:00:00"))
        self.assertIn("tasks.status", self.codes(self.check()))

    def test_old_or_wrong_case_state_directory_is_error_without_reading(self):
        self.todo.rmdir(); self.done.rmdir(); self.drop.rmdir()
        for invalid in ("待办事项", "Todo", "TODO", "Done", "DONE", "Drop", "DROP"):
            with self.subTest(invalid=invalid):
                old = self.target / invalid
                old.mkdir()
                self.write(old, text=task_text("todo"))
                with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
                    result = self.check()
                self.assertIn("tasks.state_name", self.codes(result))
                self.assertEqual(result.stats["task_files"], 0)
                next(old.iterdir()).unlink()
                old.rmdir()

    def test_wrong_case_english_directory_is_error(self):
        self.todo.rmdir(); self.done.rmdir(); self.drop.rmdir()
        (self.target / "TODO").mkdir()
        self.assertIn("tasks.state_name", self.codes(self.check()))

    def test_unrelated_misc_and_readme_are_ignored(self):
        (self.target / "misc").mkdir()
        (self.target / "README.md").write_text("导航", encoding="utf-8")
        self.assertTrue(self.check().ok)
        self.assertEqual(self.check().stats["task_files"], 0)

    def test_duplicate_identifier_across_three_states(self):
        self.write(self.todo)
        self.write(self.done, "T001-重复.md", task_text("done", completion="2026-10-02 12:00:00"))
        self.write(self.drop, "T001-重复终止.md", task_text("drop", termination="2026-10-02 12:00:00", reason="原因"))
        self.assertIn("tasks.duplicate_id", self.codes(self.check()))

    def test_missing_state_directories_are_skipped_without_creation(self):
        self.todo.rmdir(); self.done.rmdir(); self.drop.rmdir()
        before = self.snapshot()
        with patch.object(Path, "mkdir", side_effect=AssertionError("must not mkdir")):
            result = self.check()
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.stats["task_directories_skipped"], 3)
        self.assertEqual(self.snapshot(), before)

    def test_default_tasks_missing_is_normal_skip_and_explicit_missing_errors(self):
        for directory in (self.todo, self.done, self.drop): directory.rmdir()
        self.target.rmdir(); self.target.parent.rmdir()
        result = self.check()
        self.assertTrue(result.ok)
        self.assertEqual(result.stats["task_directories_skipped"], 1)
        self.assertIn("tasks.directory_absent", self.codes(result))
        result = self.check(self.workspace / "docs" / "typo")
        self.assertFalse(result.ok)
        self.assertIn("tasks.directory_missing", self.codes(result))

    def test_invalid_calendar_and_history_exception(self):
        invalid = self.write(self.todo, text=task_text("todo", creation="2026-02-29 00:00:00"))
        self.assertIn("tasks.time_format", self.codes(self.check()))
        invalid.unlink()
        self.write(self.todo, "T002-历史.md", task_text("todo", creation="未记录", update="未记录"))
        self.assertNotIn("tasks.time_format", self.codes(self.check()))
        self.assertTrue(self.check().ok)

    def test_code_blocks_do_not_supply_metadata(self):
        self.write(self.todo, text="```markdown\n" + task_text("done") + "```\n")
        self.assertTrue({"tasks.title", "tasks.status", "tasks.time_missing"} <= self.codes(self.check()))

    def test_boundary_rejection_happens_without_reading(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
            result = self.check(sources=[self.workspace])
        self.assertFalse(result.ok)
        self.assertIn("tasks.source_boundary", self.codes(result))

    def test_nested_git_rejection_without_reading(self):
        (self.workspace / ".git").mkdir()
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
            result = self.check()
        self.assertIn("tasks.nested_repository", self.codes(result))


if __name__ == "__main__":
    unittest.main()
