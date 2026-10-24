"""Exercise real signed Git operations with local remotes and a mocked API."""

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.dont_write_bytecode = True

import git_submit as tool


SCRATCH = None


def snapshot(folder):
    return {
        str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        for path in folder.rglob("*")
    }


class GitWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workflow-", dir=SCRATCH)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "source"
        self.remote = self.root / "remote.git"
        self.repo.mkdir()
        self.environment = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Synthetic Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Synthetic Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GITHUB_TOKEN": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.command("git", "init", "--initial-branch=main", str(self.repo))
        self.command("git", "init", "--bare", "--initial-branch=main", str(self.remote))
        key = self.root / "signing-key"
        self.command("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "synthetic", "-f", str(key))
        allowed = self.root / "allowed_signers"
        allowed.write_text("test@example.invalid " + key.with_suffix(".pub").read_text(encoding="utf-8"), encoding="utf-8")
        for name, value in (
            ("user.name", "Synthetic Test"), ("user.email", "test@example.invalid"),
            ("gpg.format", "ssh"), ("user.signingkey", str(key)),
            ("gpg.ssh.allowedSignersFile", str(allowed)),
            ("gpg.ssh.program", shutil.which("ssh-keygen")),
        ):
            self.git("config", name, value)
        self.git("remote", "add", "origin", str(self.remote))
        self.stage("change.txt", "first change\n")

    @staticmethod
    def command(*arguments):
        result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8")
        if result.returncode:
            raise AssertionError((arguments, result.returncode, result.stdout, result.stderr))
        return result.stdout.strip()

    def git(self, *arguments):
        return self.command("git", "-C", str(self.repo), *arguments)

    def stage(self, name, text):
        (self.repo / name).write_text(text, encoding="utf-8")
        self.git("add", "--", name)

    def api(self, repository, commit):
        return {"sha": commit, "verification": {"verified": True, "reason": "valid"}}

    def invoke(self, command, *extra, api=None):
        args = [command, "--repo", str(self.repo), "--remote", "origin", "--branch", "main", "--format", "json", *extra]
        output = io.StringIO()
        with patch.object(tool, "github_repository", return_value="example/project"), \
                patch.object(tool, "github_commit", side_effect=self.api if api is None else api) as request, \
                contextlib.redirect_stdout(output):
            code = tool.main(args)
        return code, json.loads(output.getvalue()), request

    def submit(self):
        code, result, request = self.invoke("submit", "--message", "提交合成变更")
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"], result)
        return result

    def test_submit_signs_staged_content_and_pushes_same_sha(self):
        (self.repo / "untracked.txt").write_text("keep local", encoding="utf-8")
        (self.repo / "change.txt").write_text("unstaged replacement\n", encoding="utf-8")
        result = self.submit()
        commit = result["commit"]
        self.assertEqual(self.git("show", f"{commit}:change.txt"), "first change")
        self.assertEqual(self.git("ls-tree", "--name-only", commit), "change.txt")
        self.assertEqual((self.repo / "change.txt").read_text(encoding="utf-8"), "unstaged replacement\n")
        self.assertEqual(self.command("git", "--git-dir", str(self.remote), "rev-parse", "refs/heads/main"), commit)
        self.git("verify-commit", commit)
        self.assertEqual(result["targets"][0]["remote_commit"], commit)
        self.assertTrue(result["targets"][0]["verified"])
        self.assertEqual(result["targets"][0]["reason"], "valid")

    def test_verify_is_read_only_and_does_not_create_or_push(self):
        commit = self.submit()["commit"]
        before = snapshot(self.root)
        code, result, request = self.invoke("verify", "--commit", commit)
        self.assertEqual(code, 0, result)
        self.assertNotIn("commit", result["completed_steps"])
        self.assertNotIn("push", result["completed_steps"])
        self.assertEqual(snapshot(self.root), before)
        request.assert_called_once_with("example/project", commit)

    def test_push_existing_commit_without_creating_another_commit_or_tag(self):
        self.git("commit", "-S", "-m", "existing signed commit")
        self.git("tag", "-a", "v-test", "-m", "local tag")
        self.git("config", "push.followTags", "true")
        commit = self.git("rev-parse", "HEAD")
        code, result, request = self.invoke("push", "--commit", commit)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.git("rev-parse", "HEAD"), commit)
        self.assertNotIn("commit", result["completed_steps"])
        self.assertEqual(self.command("git", "--git-dir", str(self.remote), "tag", "--list"), "")

    def test_push_address_is_used_instead_of_fetch_address(self):
        fetch_only = self.root / "fetch.git"
        self.command("git", "init", "--bare", str(fetch_only))
        self.git("remote", "set-url", "origin", str(fetch_only))
        self.git("remote", "set-url", "--push", "origin", str(self.remote))
        result = self.submit()
        self.assertTrue(result["targets"][0]["remote_verified"])
        self.assertEqual(self.command("git", "--git-dir", str(fetch_only), "for-each-ref"), "")

    def test_each_configured_push_address_is_verified(self):
        second = self.root / "second.git"
        self.command("git", "init", "--bare", str(second))
        self.git("remote", "set-url", "--add", "--push", "origin", str(self.remote))
        self.git("remote", "set-url", "--add", "--push", "origin", str(second))
        code, result, request = self.invoke("submit", "-m", "multiple configured addresses")
        self.assertEqual(code, 0, result)
        self.assertEqual(len(result["targets"]), 2)
        self.assertEqual(request.call_count, 2)
        self.assertTrue(all(target["remote_commit"] == result["commit"] for target in result["targets"]))

    def test_local_signature_failure_stops_before_push(self):
        self.git("-c", "commit.gpgsign=false", "commit", "-m", "unsigned")
        before_remote = snapshot(self.remote)
        code, result, request = self.invoke("push")
        self.assertEqual(code, 1, result)
        self.assertEqual(result["step"], "local_verify")
        self.assertNotIn("push", result["completed_steps"])
        self.assertEqual(snapshot(self.remote), before_remote)
        request.assert_not_called()

    def test_empty_index_does_not_create_or_push_another_commit(self):
        commit = self.submit()["commit"]
        before_remote = snapshot(self.remote)
        code, result, request = self.invoke("submit", "-m", "nothing staged")
        self.assertEqual(code, 1, result)
        self.assertEqual(result["step"], "commit")
        self.assertEqual(self.git("rev-parse", "HEAD"), commit)
        self.assertEqual(snapshot(self.remote), before_remote)
        request.assert_not_called()

    def test_rejected_push_preserves_new_local_commit(self):
        published = self.submit()["commit"]
        self.command("git", "--git-dir", str(self.remote), "config", "receive.denyNonFastForwards", "true")
        self.git("checkout", "--orphan", "separate-history")
        self.stage("change.txt", "independent change\n")
        code, result, request = self.invoke("submit", "-m", "rejected history")
        self.assertEqual(code, 1, result)
        self.assertEqual(result["step"], "push")
        self.assertIn("commit", result["completed_steps"])
        self.assertIn("local_verify", result["completed_steps"])
        self.assertNotEqual(result["commit"], published)
        self.assertEqual(self.git("rev-parse", "HEAD"), result["commit"])
        self.assertEqual(self.command("git", "--git-dir", str(self.remote), "rev-parse", "main"), published)
        request.assert_not_called()

    def test_remote_mismatch_fails_before_api_request(self):
        self.submit()
        self.stage("change.txt", "local only\n")
        self.git("commit", "-S", "-m", "not pushed")
        code, result, request = self.invoke("verify")
        self.assertEqual(code, 1, result)
        self.assertEqual(result["step"], "remote_verify")
        self.assertEqual(result["errors"][0]["code"], "remote_mismatch")
        request.assert_not_called()

    def test_github_failure_preserves_push_and_can_be_verified_later(self):
        def unverified(repository, commit):
            return {"sha": commit, "verification": {"verified": False, "reason": "unknown_key"}}
        code, result, request = self.invoke("submit", "-m", "pending verification", api=unverified)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["step"], "github_verify")
        self.assertIn("push", result["completed_steps"])
        self.assertTrue(result["targets"][0]["remote_verified"])
        self.assertEqual(result["targets"][0]["reason"], "unknown_key")
        self.assertEqual(request.call_count, 1)
        before = snapshot(self.root)
        code, verified, request = self.invoke("verify", "--commit", result["commit"])
        self.assertEqual(code, 0, verified)
        self.assertEqual(snapshot(self.root), before)

    def test_github_sha_reason_and_response_contract_must_match(self):
        commit = self.submit()["commit"]
        cases = (
            ({"sha": "different", "verification": {"verified": True, "reason": "valid"}}, "github_mismatch"),
            ({"sha": commit, "verification": {"verified": True, "reason": "unknown_key"}}, "github_signature"),
            ({"sha": commit}, "github_response"),
        )
        before = snapshot(self.root)
        for payload, error_code in cases:
            with self.subTest(error_code=error_code):
                code, result, request = self.invoke("verify", api=lambda *_: payload)
                self.assertEqual(code, 1, result)
                self.assertEqual(result["errors"][0]["code"], error_code)
                self.assertEqual(request.call_count, 1)
        self.assertEqual(snapshot(self.root), before)

    def test_message_file_preserves_multiline_text(self):
        message = self.root / "message.txt"
        message.write_text("合成提交标题\n\n第二行说明与 `字面量`。\n", encoding="utf-8")
        code, result, request = self.invoke("submit", "--message-file", str(message))
        self.assertEqual(code, 0, result)
        self.assertEqual(self.git("log", "-1", "--format=%B"), message.read_text(encoding="utf-8").strip())


class ApiTests(unittest.TestCase):
    def test_repository_is_derived_from_github_https_and_ssh(self):
        for url in ("https://github.com/example/project.git", "git@github.com:example/project.git", "ssh://git@github.com/example/project.git"):
            with self.subTest(url=url):
                self.assertEqual(tool.github_repository(url), "example/project")
        with self.assertRaises(tool.ToolError):
            tool.github_repository("https://example.invalid/example/project.git")

    def test_api_uses_exact_commit_and_optional_environment_token(self):
        response = {"sha": "abc123", "verification": {"verified": True, "reason": "valid"}}
        for token in ("", "synthetic-token"):
            with self.subTest(authenticated=bool(token)), patch.dict(os.environ, {"GITHUB_TOKEN": token}), \
                    patch.object(tool, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as request:
                self.assertEqual(tool.github_commit("example/project", "abc123"), response)
                request.assert_called_once()
                sent = request.call_args.args[0]
                self.assertEqual(sent.full_url, "https://api.github.com/repos/example/project/git/commits/abc123")
                self.assertEqual(sent.get_header("Authorization"), "Bearer synthetic-token" if token else None)

    def test_api_errors_are_reported_without_retry(self):
        for error, code in ((HTTPError("https://api.github.com", 403, "Forbidden", {}, None), "github_http"),
                            (URLError("synthetic connection error"), "github_network")):
            with self.subTest(code=code), patch.object(tool, "urlopen", side_effect=error) as request:
                with self.assertRaises(tool.ToolError) as raised:
                    tool.github_commit("example/project", "abc123")
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(request.call_count, 1)

    def test_git_diagnostics_redact_tokens_and_url_credentials(self):
        failure = subprocess.CompletedProcess([], 1, "", "https://name:password@github.com/example/project synthetic-token")
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-token"}), patch.object(tool.subprocess, "run", return_value=failure):
            with self.assertRaises(tool.ToolError) as raised:
                tool.git(Path("."), "push")
        self.assertNotIn("password", str(raised.exception))
        self.assertNotIn("synthetic-token", str(raised.exception))
        self.assertIn("Git 退出码 1", str(raised.exception))


def main():
    global SCRATCH
    parser = argparse.ArgumentParser(description="在指定批次目录运行合成 Git 提交与验证测试。")
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    SCRATCH = args.scratch.resolve()
    if not SCRATCH.is_dir():
        parser.error("--scratch 必须是调用方已准备好的测试批次目录。")
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
