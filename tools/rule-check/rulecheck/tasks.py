"""Read-only structural checks for explicitly selected workspace task records.

This module checks records, not whether their business acceptance criteria passed.
It never opens source documents, Git metadata contents, or redirected paths.
"""

from collections.abc import Sequence
from datetime import datetime
import os
from pathlib import Path
import re
import stat

from markdown_it import MarkdownIt

from .models import CheckResult
from .paths import is_redirect, is_within


_TASK_NAME = re.compile(r"^(?P<id>(?:[A-Za-z][A-Za-z0-9]*?-?\d+|\d+))[-－—_ ]+(?P<name>.+)$")
_METADATA = re.compile(r"^(状态|摘要|创建时间|最后更新时间|完成时间|终止时间|终止原因)\s*[：:]\s*(.*?)\s*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
_SECTIONS = ("工作清单", "当前进展与接续")
_STATES = ("todo", "doing", "done", "drop")
_SUMMARY_LIMIT = 120
_LEGACY_STATE_NAMES = {
    "待办", "待办事项", "完成", "完成事项", "已完成", "终止", "终止事项", "已终止", "进行中",
    "TODO", "DONE", "DROP",
}


def _absolute(path: Path) -> Path:
    """Normalize dot segments without resolving redirects."""
    return Path(os.path.abspath(path))


def _redirect_in_path(path: Path) -> Path | None:
    # Include the selected root and its ancestors, not just descendants.
    for candidate in reversed((path, *path.parents)):
        if is_redirect(candidate):
            return candidate
    return None


def _git_marker(directory: Path) -> bool:
    # lstat detects broken redirected markers and preserves access errors.
    try:
        (directory / ".git").lstat()
    except FileNotFoundError:
        return False
    return True


def _directory_presence(path: Path, result: CheckResult) -> bool | None:
    """Distinguish absent paths from files and errors in any parent component."""
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISDIR(info.st_mode):
            result.add("tasks.directory_type", "事项路径或父组件不是目录。", component)
            return None
    return True


def _validate_roots(
    workspace: Path, source_repos: Sequence[Path], tasks_dir: Path, result: CheckResult,
    default_target: bool,
) -> bool:
    if not source_repos:
        result.add("tasks.source_required", "必须显式提供至少一个源码仓库。")
        return False
    for label, path in (("工作区", workspace), ("事项目录", tasks_dir)):
        redirect = _redirect_in_path(path)
        if redirect is not None:
            result.add("tasks.redirect", f"{label}路径包含符号链接或 junction，拒绝跟随。", redirect)
            return False
    for source in source_repos:
        redirect = _redirect_in_path(source)
        if redirect is not None:
            result.add("tasks.redirect", "声明的源码仓库路径包含符号链接或 junction。", redirect)
            return False
    if not workspace.is_dir():
        result.add("tasks.workspace", "工作区不存在或不是目录。", workspace)
        return False
    if not is_within(tasks_dir, workspace):
        result.add("tasks.outside_workspace", "事项目录必须位于显式指定的工作区内。", tasks_dir)
        return False
    for source in source_repos:
        if is_within(tasks_dir, source) or is_within(source, tasks_dir):
            result.add("tasks.source_boundary", "事项目录不能位于源码仓库内，也不能包含源码仓库。", tasks_dir)
            return False
        if not source.is_dir():
            result.add("tasks.source_missing", "声明的源码仓库不存在或不是目录。", source)
            return False
    present = _directory_presence(tasks_dir, result)
    if present is None:
        return False
    # A .git file is a repository marker just as much as a .git directory.
    current = tasks_dir
    while True:
        if _git_marker(current):
            result.add("tasks.nested_repository", "事项路径属于未声明的 Git 仓库，拒绝读取。", current)
            return False
        if current.parent == current:
            break
        current = current.parent
    if not present:
        if default_target:
            result.stats["task_directories_skipped"] += 1
            result.add("tasks.directory_absent", "默认事项目录不存在，尚无事项，已跳过。", tasks_dir, severity="info")
        else:
            result.add("tasks.directory_missing", "显式指定的事项目录不存在。", tasks_dir)
        return False
    return True


def _task_files(
    directory: Path, workspace: Path, sources: Sequence[Path], result: CheckResult
):
    """Enumerate only this state directory, pruning repositories and redirects."""
    try:
        info = directory.lstat()
    except FileNotFoundError:
        return
    if is_redirect(directory):
        result.add("tasks.redirect", "发现符号链接或 junction，拒绝跟随。", directory)
        return
    if not stat.S_ISDIR(info.st_mode):
        result.add("tasks.state_directory", "事项状态路径不是目录。", directory)
        return
    if not is_within(directory, workspace) or any(
        is_within(directory, source) for source in sources
    ):
        result.add("tasks.source_boundary", "事项路径超出工作区或进入源码仓库，拒绝读取。", directory)
        return
    if _git_marker(directory):
        result.add("tasks.nested_repository", "发现未声明的嵌套 Git 仓库，拒绝扫描。", directory)
        return
    try:
        children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        result.add("tasks.scan_failed", f"无法扫描事项目录（{type(exc).__name__}）。", directory)
        return
    for child in children:
        if is_redirect(child):
            result.add("tasks.redirect", "发现符号链接或 junction，拒绝跟随。", child)
        elif stat.S_ISDIR(child.lstat().st_mode):
            yield from _task_files(child, workspace, sources, result)
        elif child.suffix.lower() == ".md" and child.name.casefold() != "readme.md":
            yield child


def _state_directories(target: Path, result: CheckResult):
    """Return exact-case todo/doing/done/drop entries without opening other dirs."""
    try:
        entries = list(target.iterdir())
    except OSError as exc:
        result.add("tasks.scan_failed", f"无法扫描事项目录（{type(exc).__name__}）。", target)
        return {}
    found = {}
    for entry in entries:
        if entry.name in _STATES:
            found[entry.name] = entry
            continue
        folded = entry.name.casefold()
        if folded in {name.casefold() for name in _STATES} or entry.name in _LEGACY_STATE_NAMES:
            result.add("tasks.state_name", "事项状态目录必须精确命名为 todo、doing、done 或 drop；旧名称或大小写错误不会被读取。", entry)
    return found


def _inline_text(token) -> str:
    return "".join(
        child.content for child in token.children or ()
        if child.type in {"text", "code_inline"}
    ).strip()


def _structure(text: str):
    """Get actual headings and top-level paragraph metadata, ignoring code."""
    tokens = MarkdownIt("commonmark").parse(text)
    headings = []
    paragraph_lines = set()
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.level == 0:
            inline = tokens[index + 1]
            headings.append((token.tag, _inline_text(inline), token.map[0] + 1))
        elif token.type == "paragraph_open" and token.level == 0 and token.map:
            paragraph_lines.update(range(token.map[0], token.map[1]))
    metadata = {}
    for index, line in enumerate(text.splitlines()):
        if index not in paragraph_lines:
            continue
        match = _METADATA.fullmatch(line.strip())
        if match:
            metadata.setdefault(match[1], []).append((match[2], index + 1))
    return headings, metadata


def _check_document(path: Path, state: str, result: CheckResult) -> None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        result.add("tasks.read_failed", f"无法读取 UTF-8 事项文件（{type(exc).__name__}）。", path)
        return
    result.stats["task_files"] += 1
    headings, metadata = _structure(text)
    titles = [heading for heading in headings if heading[0] == "h1"]
    if len(titles) != 1 or not titles[0][1] or re.fullmatch(r"<[^>]+>", titles[0][1]):
        result.add("tasks.title", "事项正文必须有一个非空的一级标题。", path)
    for section in _SECTIONS:
        if not any(tag == "h2" and name == section for tag, name, _ in headings):
            result.add("tasks.section", f"缺少二级章节：{section}。", path)
    for key, values in metadata.items():
        if len(values) > 1:
            result.add("tasks.metadata_duplicate", f"{key}只能记录一次。", path, values[1][1])
    statuses = metadata.get("状态", [])
    if not statuses:
        result.add("tasks.status", "缺少正文状态记录。", path)
    else:
        if statuses[0][0] != state:
            result.add("tasks.status", f"状态必须与目录名 {state} 完全一致。", path, statuses[0][1])
    summaries = metadata.get("摘要", [])
    if not summaries or not summaries[0][0].strip():
        result.add("tasks.summary", "事项必须有一行非空摘要，用于快速识别变更结果。", path)
    elif len(summaries[0][0]) > _SUMMARY_LIMIT:
        result.add("tasks.summary", f"摘要不能超过 {_SUMMARY_LIMIT} 个字符。", path, summaries[0][1])
    footer = ["创建时间", "最后更新时间"]
    if state in ("todo", "doing"):
        forbidden = ("完成时间", "终止时间")
    elif state == "done":
        footer.append("完成时间")
        forbidden = ("终止时间",)
    else:
        footer.append("终止时间")
        forbidden = ("完成时间",)
        reasons = metadata.get("终止原因", [])
        if not reasons or not reasons[0][0].strip():
            result.add("tasks.termination_reason", "drop 事项必须有非空顶层终止原因。", path)
    for key in forbidden:
        if key in metadata:
            result.add("tasks.forbidden_time", f"{state}事项不能记录{key}。", path, metadata[key][0][1])
    dates = {}
    for key in footer:
        values = metadata.get(key, [])
        if not values:
            result.add("tasks.time_missing", f"缺少文末时间记录：{key}。", path)
            continue
        value, line = values[0]
        if value == "未记录":
            continue
        try:
            if not _DATE.fullmatch(value):
                raise ValueError("format")
            dates[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            result.add("tasks.time_format", f"{key}必须是真实日历时间 yyyy-mm-dd hh:mm:ss，或历史例外“未记录”。", path, line)
    nonblank_lines = [index + 1 for index, line in enumerate(text.splitlines()) if line.strip()]
    recorded_lines = [metadata[key][0][1] for key in footer if key in metadata]
    if len(recorded_lines) == len(footer) and nonblank_lines[-len(footer):] != recorded_lines:
        result.add("tasks.time_footer", "时间记录必须按创建、最后更新及状态对应的完成/终止时间顺序置于文档最后。", path)
    if "创建时间" in dates and "最后更新时间" in dates and dates["创建时间"] > dates["最后更新时间"]:
        result.add("tasks.time_order", "创建时间不能晚于最后更新时间。", path)
    terminal = "完成时间" if state == "done" else "终止时间" if state == "drop" else None
    if terminal and terminal in dates and "最后更新时间" in dates and dates[terminal] > dates["最后更新时间"]:
        result.add("tasks.time_order", f"{terminal}不能晚于最后更新时间。", path)


def check_tasks(
    workspace: Path, source_repos: Sequence[Path], tasks_dir: Path | None = None
) -> CheckResult:
    """Check task structure under a safe explicit workspace; never modify inputs.

    Repository roots may equal the workspace: that declaration intentionally
    rejects workspace task scanning. Sources must be supplied by the caller;
    this function does not guess source roots from the current working directory.
    A missing default task directory means no tasks yet and is skipped without
    creating directories. A missing explicitly selected directory is an error.
    """
    result = CheckResult(stats={"task_files": 0, "task_directories_skipped": 0})
    workspace = _absolute(Path(workspace))
    sources = tuple(_absolute(Path(source)) for source in source_repos)
    target = _absolute(Path(tasks_dir)) if tasks_dir is not None else workspace / "docs" / "tasks"
    try:
        if not _validate_roots(workspace, sources, target, result, tasks_dir is None):
            return result
        identifiers = {}
        state_dirs = _state_directories(target, result)
        for state in _STATES:
            directory = state_dirs.get(state)
            if directory is None:
                result.stats["task_directories_skipped"] += 1
                continue
            for path in _task_files(directory, workspace, sources, result):
                match = _TASK_NAME.fullmatch(path.stem)
                if not match or not match["name"].strip() or not any(character.isalnum() for character in match["name"]):
                    result.add("tasks.filename", "无法识别稳定编号和用途名称；支持 001-用途.md、T001-用途.md、BUG-42-用途.md 等常见形式。", path)
                else:
                    identifier = match["id"].upper()
                    if identifier in identifiers:
                        result.add("tasks.duplicate_id", f"事项编号 {identifier} 重复，另一文件：{identifiers[identifier]}", path)
                    else:
                        identifiers[identifier] = path
                # Recheck the complete path immediately before opening content.
                if _redirect_in_path(path) is not None or not is_within(path, workspace) or any(is_within(path, source) for source in sources):
                    result.add("tasks.unsafe_file", "事项完整路径不安全，拒绝读取。", path)
                    continue
                _check_document(path, state, result)
    except OSError as exc:
        result.add("tasks.scan_failed", f"无法检查事项路径（{type(exc).__name__}）。", target)
    return result
