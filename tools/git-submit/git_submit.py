#!/usr/bin/env python3
"""Sign staged changes, push a commit, and verify its GitHub signature."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def redact(text: str) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        text = text.replace(token, "<redacted>")
    return re.sub(r"(https?://)[^/\s]+@", r"\1<redacted>@", text)


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        detail = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise ToolError("git_failed", redact(f"Git 退出码 {result.returncode}：{detail}"))
    return result.stdout.strip()


def github_repository(url: str) -> str:
    if url.startswith("git@github.com:"):
        path = url[len("git@github.com:"):]
    else:
        parsed = urlsplit(url)
        if parsed.hostname != "github.com" or parsed.scheme not in ("https", "ssh"):
            raise ToolError("github_remote", "推送地址须为 GitHub.com 的 HTTPS 或 SSH 仓库地址。")
        path = parsed.path.lstrip("/")
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        raise ToolError("github_remote", "无法从推送地址识别 GitHub owner/repo。")
    return path


def github_commit(repository: str, commit: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Potccv-git-submit",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{quote(repository, safe='/')}/git/commits/{commit}"
    try:
        with urlopen(Request(url, headers=headers)) as response:
            return json.load(response)
    except HTTPError as error:
        raise ToolError("github_http", f"GitHub API 返回 HTTP {error.code}：{error.reason}") from error
    except URLError as error:
        raise ToolError("github_network", redact(f"GitHub API 请求失败：{error.reason}")) from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ToolError("github_response", "GitHub API 未返回有效 JSON。") from error


def execute(args: argparse.Namespace, result: dict) -> None:
    repo = Path(args.repo).expanduser().resolve()
    result["repo"] = str(repo)
    result["step"] = "prepare"
    ref = f"refs/heads/{args.branch}"
    git(repo, "check-ref-format", ref)
    urls = git(repo, "remote", "get-url", "--push", "--all", "--", args.remote).splitlines()
    for url in urls:
        result["targets"].append({"repository": github_repository(url)})
    result["completed_steps"].append("prepare")

    if args.command == "submit":
        result["step"] = "commit"
        message = ["--file", str(Path(args.message_file).expanduser().resolve())] if args.message_file else ["--message", args.message]
        git(repo, "commit", "-S", *message)
        result["completed_steps"].append("commit")

    result["step"] = "resolve_commit"
    revision = "HEAD" if args.command == "submit" else args.commit
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}")
    result["commit"] = commit
    result["step"] = "local_verify"
    git(repo, "verify-commit", commit)
    result["completed_steps"].append("local_verify")

    if args.command in ("submit", "push"):
        result["step"] = "push"
        git(repo, "push", "--no-follow-tags", "--", args.remote, f"{commit}:{ref}")
        result["completed_steps"].append("push")

    for url, target in zip(urls, result["targets"]):
        result["step"] = "remote_verify"
        remote_refs = git(repo, "ls-remote", "--refs", "--exit-code", "--", url, ref)
        refs = dict((name, sha) for sha, name in (line.split() for line in remote_refs.splitlines()))
        target["remote_commit"] = refs.get(ref)
        if target["remote_commit"] != commit:
            raise ToolError("remote_mismatch", f"{target['repository']} 的 {ref} 未指向目标提交 {commit}。")
        target["remote_verified"] = True

        result["step"] = "github_verify"
        payload = github_commit(target["repository"], commit)
        try:
            api_commit = payload["sha"]
            verification = payload["verification"]
            target["verified"] = verification["verified"]
            target["reason"] = verification["reason"]
        except (KeyError, TypeError) as error:
            raise ToolError("github_response", "GitHub API 响应缺少提交 SHA 或签名验证字段。") from error
        if api_commit != commit:
            raise ToolError("github_mismatch", "GitHub API 返回的提交 SHA 与目标提交不一致。")
        if target["verified"] is not True or target["reason"] != "valid":
            raise ToolError("github_signature", f"{target['repository']} 签名未通过：{target['reason']}。")
        target["url"] = f"https://github.com/{target['repository']}/commit/{commit}"

    result["completed_steps"].extend(("remote_verify", "github_verify"))
    result["step"] = "complete"
    result["ok"] = True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="签名提交、推送并验证远端分支及 GitHub 签名。")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("submit", "提交已暂存内容，推送并验证"),
        ("push", "推送已有提交并验证"),
        ("verify", "只读核验已有提交、远端分支和 GitHub 签名"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--repo", required=True, help="目标源码仓库路径")
        command.add_argument("--remote", required=True, help="目标仓库中配置的远端名称")
        command.add_argument("--branch", required=True, help="目标远端分支名称")
        command.add_argument("--format", choices=("text", "json"), default="text")
        if name == "submit":
            message = command.add_mutually_exclusive_group(required=True)
            message.add_argument("-m", "--message", help="提交说明")
            message.add_argument("-F", "--message-file", help="提交说明文件路径")
        else:
            command.add_argument("--commit", default="HEAD", help="目标提交或引用，默认 HEAD")
    return parser


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    result = {
        "ok": False, "command": args.command, "repo": args.repo,
        "remote": args.remote, "branch": args.branch, "commit": None,
        "step": "prepare", "completed_steps": [], "targets": [],
    }
    try:
        execute(args, result)
    except ToolError as error:
        result["errors"] = [{"code": error.code, "message": redact(str(error))}]
    except (OSError, UnicodeError) as error:
        result["errors"] = [{"code": "execution_failed", "message": redact(str(error))}]
    if args.format == "json":
        print(redact(json.dumps(result, ensure_ascii=False, indent=2)))
    elif result["ok"]:
        print(f"通过：{args.command} {result['commit']} -> {args.remote}/{args.branch}")
        for target in result["targets"]:
            print(f"{target['repository']}: remote={target['remote_commit']} verified=true reason=valid")
    else:
        print(f"失败阶段：{result['step']}；目标提交：{result['commit'] or '尚未确定'}")
        print("已完成：" + ", ".join(result["completed_steps"]))
        for error in result["errors"]:
            print(f"{error['code']}: {error['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
