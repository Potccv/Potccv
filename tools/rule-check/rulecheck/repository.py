"""Read-only checks for the constraint repository's working-tree documents."""

import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
from urllib.parse import unquote, urlsplit

from .markdown import MarkdownDocument, parse_markdown
from .models import CheckResult
from .paths import contains_redirect, is_redirect, is_within


def _private_path(path: str) -> bool:
    relative = PurePosixPath(path)
    name = relative.name.casefold()
    if fnmatch.fnmatchcase(name, "*.local.*"):
        return True
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    return bool(relative.parts and relative.parts[0].casefold() == "profile"
                and path not in {"profile/README.md", "profile/AGENTS.md", "profile/example.json"})


def _markdown_path(path: str) -> bool:
    return PurePosixPath(path).suffix.casefold() in {".md", ".markdown"}


def _git(repo: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    ).stdout


def _check_example(repo: Path, tracked: set[str], result: CheckResult) -> None:
    relative = "profile/example.json"
    if relative not in tracked:
        result.add("profile_example_missing", "The public profile example must be tracked.", relative)
        return
    target = repo / relative
    if contains_redirect(target, repo) or not is_within(target, repo):
        result.stats["skipped_redirects"] += 1
        result.add("profile_example_redirect", "The public example redirects and was not read.", relative)
        return
    try:
        content = json.loads(target.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        result.add("profile_example_json", "The public example is not valid JSON.", relative, error.lineno)
        return
    except (OSError, UnicodeError):
        result.add("profile_example_read", "The public example could not be read as UTF-8.", relative)
        return
    result.stats["profile_examples_checked"] += 1
    structure = {
        "schema_version": int,
        "identity": {"display_name": str},
        "paths": {key: str for key in (
            "workspace_root", "ssh_private_key", "ssh_signing_public_key", "ssh_allowed_signers"
        )},
        "credentials": {"file": str, "values": dict},
        "preferences": {
            "auto_commit_and_push": bool,
            "subagents": {"count": int, "model": str, "reasoning_effort": str},
        },
        **{key: dict for key in ("hosts", "devices", "services", "contacts", "project_locations")},
    }

    def validate(value, shape, field=""):
        if isinstance(shape, dict):
            if type(value) is not dict:
                result.add("profile_example_type", f"Expected an object at {field or 'root'}.", relative)
                return
            if set(value) != set(shape):
                result.add("profile_example_schema", f"Unexpected or missing fields at {field or 'root'}.", relative)
            for key, expected in shape.items():
                if key in value:
                    validate(value[key], expected, f"{field}.{key}" if field else key)
        elif type(value) is not shape:
            result.add("profile_example_type", f"Invalid type at {field}.", relative)
        elif field == "schema_version":
            if value != 1:
                result.add("profile_example_version", "Unsupported example schema version.", relative)
        elif field == "preferences.auto_commit_and_push":
            if value:
                result.add("profile_example_default", "The public example must default automatic commit to false.", relative)
        elif field == "preferences.subagents.count":
            if value < 1:
                result.add("profile_example_default", "The subagent count must be a positive integer.", relative)
        elif field in {"preferences.subagents.model", "preferences.subagents.reasoning_effort"}:
            if not value.strip():
                result.add("profile_example_default", f"The generic default at {field} must be nonempty.", relative)
        elif value:
            result.add("profile_example_not_empty", f"Personal example data at {field} must be empty.", relative)

    validate(content, structure)


def check_repository(repo: Path) -> CheckResult:
    """Check tracked public Markdown, local links, AGENTS reachability and example JSON.

    Git's index supplies names; contents always come from the working tree.
    No target is modified and no external URL is requested.
    """
    result = CheckResult(stats={key: 0 for key in (
        "tracked_paths", "markdown_files", "markdown_targets_read", "links", "local_links",
        "external_links", "skipped_outside_links", "skipped_redirects", "skipped_private_links",
        "private_tracked_paths", "agents_files", "agents_reachable", "profile_examples_checked",
    )})
    raw_root = Path(os.path.abspath(repo))
    if is_redirect(raw_root) or contains_redirect(raw_root, Path(raw_root.anchor)):
        result.add("repository_redirect", "The repository path redirects and was not scanned.", raw_root)
        return result
    root = raw_root.resolve()
    try:
        actual = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
        if actual != root:
            result.add("repository_root", "The input must be the Git repository root.", root)
            return result
        names = _git(root, "ls-files", "-z").split(b"\0")
    except (OSError, subprocess.CalledProcessError):
        result.add("repository_git", "Could not verify the Git repository and its tracked paths.", root)
        return result
    tracked = {os.fsdecode(name).replace("\\", "/") for name in names if name}
    result.stats["tracked_paths"] = len(tracked)
    public = set()
    for relative in sorted(tracked):
        if _private_path(relative):
            result.stats["private_tracked_paths"] += 1
            result.add("private_tracked_path", "A private path is Git-tracked; its contents were not read.", relative)
            continue
        public.add(relative)
        parts = PurePosixPath(relative).parts
        if parts and parts[0] == "rules" and relative not in {"rules/AGENTS.md", "rules/README.md"}:
            if len(parts) < 3 or parts[1] not in {"repo", "workspace"}:
                result.add("rule_location", "Detailed rule files must be under rules/repo or rules/workspace.", relative)

    documents: dict[str, MarkdownDocument] = {}

    def read_document(relative: str):
        if relative in documents:
            return documents[relative]
        path = root / relative
        if contains_redirect(path, root) or not is_within(path, root):
            result.stats["skipped_redirects"] += 1
            result.add("markdown_redirect", "A redirected Markdown path was not read.", relative, severity="warning")
            return None
        try:
            document = parse_markdown(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError):
            result.add("markdown_read", "A Markdown document could not be read as UTF-8.", relative)
            return None
        documents[relative] = document
        result.stats["markdown_targets_read"] += 1
        return document

    markdown_names = sorted(path for path in public if _markdown_path(path))
    for relative in markdown_names:
        read_document(relative)
    result.stats["markdown_files"] = len(markdown_names)
    agents = {path for path in markdown_names if PurePosixPath(path).name == "AGENTS.md"}
    edges: dict[str, set[str]] = {path: set() for path in agents}
    for source in markdown_names:
        document = documents.get(source)
        if document is None:
            continue
        for link in document.links:
            result.stats["links"] += 1
            try:
                url = urlsplit(link.target)
            except ValueError:
                result.add("link_invalid", "The link target is not a valid URL or local path.", source, link.line)
                continue
            if url.scheme or url.netloc:
                result.stats["external_links"] += 1
                continue
            result.stats["local_links"] += 1
            raw_path = unquote(url.path)
            if not raw_path:
                target = root / source
            elif raw_path.startswith("/") and not raw_path.startswith("//"):
                target = root / raw_path[1:]
            else:
                target = (root / source).parent / raw_path
            # Check components before normalization: a redirect followed by '..' is unsafe too.
            lexical = Path(os.path.abspath(target))
            if not lexical.is_relative_to(root):
                result.stats["skipped_outside_links"] += 1
                result.add("link_outside", "A link outside the repository was not read.", source, link.line, "warning")
                continue
            if contains_redirect(target, root) or not is_within(target, root):
                result.stats["skipped_redirects"] += 1
                result.add("link_redirect", "A redirected link target was not read.", source, link.line, "warning")
                continue
            relative = lexical.relative_to(root).as_posix()
            if _private_path(relative):
                result.stats["skipped_private_links"] += 1
                result.add("link_private", "A private link target was not read.", source, link.line, "warning")
                continue
            if not lexical.exists():
                result.add("link_missing", f"Local link target does not exist: {relative}", source, link.line)
                continue
            if lexical.is_file() and relative not in public:
                result.add("link_untracked", f"Local file link target is not Git-tracked: {relative}", source, link.line)
                continue
            if source in agents and relative in agents and not link.image:
                edges[source].add(relative)
            if url.fragment:
                if _markdown_path(relative) and lexical.is_file():
                    target_document = read_document(relative)
                    if target_document is not None and unquote(url.fragment) not in target_document.anchors:
                        result.add("anchor_missing", f"Local heading or custom anchor is missing in {relative}.", source, link.line)
                else:
                    result.add("anchor_unchecked", "Anchors in non-Markdown targets are not checked.", source, link.line, "warning")

    reachable = set()
    pending = ["AGENTS.md"] if "AGENTS.md" in agents and "AGENTS.md" in documents else []
    while pending:
        source = pending.pop()
        if source not in reachable:
            reachable.add(source)
            pending.extend(edges[source] - reachable)
    if "AGENTS.md" not in agents:
        result.add("agents_root_missing", "The Git-tracked root AGENTS.md entry is required.", "AGENTS.md")
    for relative in sorted(agents - reachable):
        result.add("agents_unreachable", "AGENTS.md is unreachable from the root AGENTS link graph.", relative)
    result.stats["agents_files"] = len(agents)
    result.stats["agents_reachable"] = len(reachable)
    _check_example(root, tracked, result)
    return result
