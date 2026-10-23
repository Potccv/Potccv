import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from rulecheck.repository import check_repository
from tests.support import temporary_directory


def example_profile():
    return {
        "schema_version": 1,
        "identity": {"display_name": ""},
        "paths": {key: "" for key in (
            "workspace_root", "ssh_private_key", "ssh_signing_public_key", "ssh_allowed_signers"
        )},
        "credentials": {"file": "", "values": {}},
        "preferences": {
            "auto_commit_and_push": False,
            "release": {"create_after_change": True, "auto_push": False},
            "subagents": {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
        },
        **{key: {} for key in ("hosts", "devices", "services", "contacts", "project_locations")},
    }


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.scratch = temporary_directory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        self.git("init", "--quiet")
        self.write("AGENTS.md", "# Entry\n[profile](profile/AGENTS.md)\n[rules](rules/AGENTS.md)\n[tools](tools/AGENTS.md)\n")
        self.write("profile/AGENTS.md", "# Profile entry\n[configuration](configuration.md)\n[fields](fields.md)\n[maintenance](maintenance.md)\n")
        self.write("profile/configuration.md", "# Profile\n[example](example.json)\n")
        self.write("profile/fields.md", "# Fields\n")
        self.write("profile/maintenance.md", "# Maintenance\n")
        self.write("rules/AGENTS.md", "# Rules entry\n[scope](scope.md)\n[maintenance](maintenance.md)\n[repo](repo/AGENTS.md)\n[workspace](workspace/AGENTS.md)\n")
        self.write("rules/scope.md", "# Rules\n")
        self.write("rules/maintenance.md", "# Rule maintenance\n")
        self.write("rules/repo/AGENTS.md", "# Repo entry\n[coding](coding.md)\n")
        self.write("rules/repo/coding.md", "# Repo\n")
        self.write("rules/workspace/AGENTS.md", "# Workspace entry\n[layout](layout.md)\n")
        self.write("rules/workspace/layout.md", "# Workspace\n")
        self.write("tools/AGENTS.md", "# Tools entry\n[tool](rule-check/AGENTS.md)\n[usage](rule-check/README.md)\n")
        self.write("tools/rule-check/AGENTS.md", "# Tool\n")
        self.write("tools/rule-check/README.md", "# Tool usage\n")
        self.write("profile/example.json", json.dumps(example_profile()))
        self.git("add", ".")

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.root), *arguments], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def write(self, relative, text):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def codes(self, result):
        return {issue.code for issue in result.issues}

    def test_valid_hierarchical_entries_and_empty_legacy_directory(self):
        (self.root / "rules/old-layout").mkdir()
        result = check_repository(self.root)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.stats["agents_files"], 7)
        self.assertEqual(result.stats["agents_reachable"], 7)
        self.assertEqual(result.stats["rule_files"], 7)
        self.assertEqual(result.stats["rules_reachable"], 7)
        self.assertEqual(result.stats["profile_examples_checked"], 1)

    def test_requires_actual_git_root(self):
        self.assertEqual(self.codes(check_repository(self.root / "rules")), {"repository_root"})
        unrelated = Path(self.scratch.name) / "unrelated"
        unrelated.mkdir()
        self.assertEqual(self.codes(check_repository(unrelated)), {"repository_git"})

    def test_worktree_links_reference_images_and_duplicate_anchors(self):
        self.write("Guide 文档.md", "# 中文 **标题**\n# Same\n# Same\n<a id='custom'></a>\n")
        self.write("picture.bin", "synthetic image placeholder")
        self.write("README.md", "# Original\n")
        self.git("add", ".")
        # Index names are reused, but these unstaged links must be checked.
        self.write("README.md",
                   "[Chinese][guide]\n[duplicate](Guide%20文档.md#same-1)\n"
                   "[custom](Guide%20文档.md#custom)\n![picture](picture.bin)\n\n"
                   "[guide]: <Guide 文档.md#中文-标题>\n\n"
                   "```md\n[example](absent.md)\n```\n")
        result = check_repository(self.root)
        self.assertTrue(result.ok, result.issues)
        self.write("README.md", "[bad](absent.md)\n![bad image](absent.png)\n[bad anchor](Guide%20文档.md#wrong)\n")
        result = check_repository(self.root)
        self.assertEqual(sum(issue.code == "link_missing" for issue in result.issues), 2)
        self.assertIn("anchor_missing", self.codes(result))

    def test_external_and_outside_links_are_counted_without_reading(self):
        outside = Path(self.scratch.name) / "outside.md"
        outside.write_text("# Outside", encoding="utf-8")
        self.write("README.md", "[site](https://example.invalid/x#any)\n"
                   "[mail](mailto:nobody@example.invalid)\n[outside](../outside.md#outside)\n")
        self.git("add", "README.md")
        original_read = Path.read_text

        def guarded_read(path, *args, **kwargs):
            self.assertNotEqual(path.resolve(), outside.resolve(), "Outside content must not be read")
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read):
            result = check_repository(self.root)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.stats["external_links"], 2)
        self.assertEqual(result.stats["skipped_outside_links"], 1)
        self.assertIn("link_outside", self.codes(result))

    def test_untracked_markdown_target_is_not_read_or_accepted(self):
        self.write("untracked.md", "# Not published\n")
        self.write("README.md", "[untracked](untracked.md#not-published)\n")
        self.git("add", "README.md")
        original_read = Path.read_text

        def guarded_read(path, *args, **kwargs):
            self.assertNotEqual(path.name, "untracked.md")
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read):
            result = check_repository(self.root)
        self.assertIn("link_untracked", self.codes(result))
        self.assertFalse(result.ok)

    def test_root_relative_links_use_repository_root_and_check_missing_targets(self):
        self.write("AGENTS.md", "# Entry\n[profile](/profile/AGENTS.md)\n[rules](/rules/AGENTS.md)\n[tools](/tools/AGENTS.md)\n")
        self.write("rules/repo/coding.md", "# Repo\n[root](/AGENTS.md#entry)\n")
        result = check_repository(self.root)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.stats["agents_reachable"], 7)
        self.assertEqual(result.stats["rules_reachable"], 7)
        self.assertEqual(result.stats["skipped_outside_links"], 0)
        self.write("rules/repo/coding.md", "# Repo\n[missing](/missing.md)\n")
        result = check_repository(self.root)
        self.assertIn("link_missing", self.codes(result))
        self.assertEqual(result.stats["skipped_outside_links"], 0)

    def test_untracked_image_is_rejected_without_reading_binary_content(self):
        image = self.root / "picture.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n\xffsynthetic")
        self.write("README.md", "![image](picture.png)\n[directory](rules/)\n")
        self.git("add", "README.md")
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def guarded_read_text(path, *args, **kwargs):
            self.assertNotEqual(path, image)
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path, *args, **kwargs):
            self.assertNotEqual(path, image)
            return original_read_bytes(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read_text), patch.object(Path, "read_bytes", guarded_read_bytes):
            result = check_repository(self.root)
        self.assertEqual([issue.code for issue in result.issues], ["link_untracked"])
        self.git("add", "picture.png")
        with patch.object(Path, "read_text", guarded_read_text), patch.object(Path, "read_bytes", guarded_read_bytes):
            result = check_repository(self.root)
        self.assertTrue(result.ok, result.issues)

    def test_private_tracked_paths_report_names_without_reading(self):
        private_paths = {
            "profile/local.json", "profile/notes.md", "profile/nested/AGENTS.md",
            "profile/nested/notes.md", "profile/nested/configuration.md", "profile/README.MD",
            "config.local.json", ".env", ".env.production",
        }
        for name in private_paths:
            self.write(name, "synthetic secret sentinel")
        self.write(".env.example", "synthetic generic example")
        self.write("README.md", "[private](profile/local.json)\n")
        self.git("add", ".")
        original_read = Path.read_text

        def guarded_read(path, *args, **kwargs):
            self.assertNotIn(path.relative_to(self.root).as_posix(), private_paths)
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read):
            result = check_repository(self.root)
        self.assertEqual(result.stats["private_tracked_paths"], len(private_paths))
        self.assertEqual(result.stats["skipped_private_links"], 1)
        self.assertEqual({issue.path for issue in result.issues if issue.code == "private_tracked_path"}, private_paths)
        self.assertNotIn("synthetic secret sentinel", repr(result.issues))

    def test_rule_links_reach_topics_and_directory_agents(self):
        self.write("rules/repo/topic.md", "# Topic\n[tool](../../tools/example/AGENTS.md)\n")
        self.write("tools/example/AGENTS.md", "# Tool\n")
        self.write("rules/repo/coding.md", "# Repo\n[topic](topic.md)\n")
        self.git("add", ".")
        result = check_repository(self.root)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.stats["agents_files"], 8)
        self.assertEqual(result.stats["agents_reachable"], 8)
        self.assertEqual(result.stats["rule_files"], 8)
        self.assertEqual(result.stats["rules_reachable"], 8)

    def test_readme_does_not_make_execution_rules_reachable(self):
        self.write("rules/repo/topic/AGENTS.md", "# Topic\n")
        self.write("rules/repo/topic.md", "# Topic\n[directory rule](topic/AGENTS.md)\n")
        self.write("rules/repo/README.md", "[topic](topic.md)\n")
        self.write("rules/repo/coding.md", "# Repo\n[human navigation](README.md)\n")
        self.git("add", ".")
        result = check_repository(self.root)
        self.assertIn("agents_unreachable", self.codes(result))
        self.assertEqual([issue.path for issue in result.issues if issue.code == "rule_unreachable"],
                         ["rules/repo/topic.md"])
        self.write("rules/repo/coding.md", "# Repo\n[topic](topic.md)\n")
        self.assertTrue(check_repository(self.root).ok)

    def test_rule_files_outside_two_scopes_are_errors(self):
        self.write("rules/legacy/AGENTS.md", "# Legacy\n")
        self.write("rules/extra.md", "# Extra\n")
        self.write("rules/README.md", "# Human navigation\n")
        self.git("add", ".")
        result = check_repository(self.root)
        self.assertEqual([issue.path for issue in result.issues if issue.code == "rule_location"],
                         ["rules/extra.md", "rules/legacy/AGENTS.md"])

    def test_public_profile_documents_are_checked_for_links_and_reachability(self):
        self.write("profile/README.md", "# Human navigation\n[fields](fields.md)\n")
        self.write("profile/AGENTS.md", "# Profile entry\n[configuration](configuration.md)\n[maintenance](maintenance.md)\n")
        self.write("profile/fields.md", "# Fields\n[missing anchor](maintenance.md#absent)\n")
        self.git("add", ".")
        result = check_repository(self.root)
        self.assertEqual([issue.path for issue in result.issues if issue.code == "rule_unreachable"],
                         ["profile/fields.md"])
        self.assertIn("anchor_missing", self.codes(result))
        self.assertEqual(result.stats["private_tracked_paths"], 0)

    def test_profile_schema_types_and_empty_values(self):
        for field, update, expected in (
            ("version", lambda value: value.update(schema_version=True), "profile_example_type"),
            ("missing", lambda value: value.pop("identity"), "profile_example_schema"),
            ("personal", lambda value: value["identity"].update(display_name="synthetic private sentinel"), "profile_example_not_empty"),
            ("dict", lambda value: value["credentials"].update(values={"synthetic": "sentinel"}), "profile_example_not_empty"),
            ("release_create", lambda value: value["preferences"]["release"].update(create_after_change=False), "profile_example_default"),
            ("release_push", lambda value: value["preferences"]["release"].update(auto_push=True), "profile_example_default"),
        ):
            with self.subTest(field=field):
                value = example_profile()
                update(value)
                self.write("profile/example.json", json.dumps(value))
                result = check_repository(self.root)
                self.assertIn(expected, self.codes(result))
                self.assertNotIn("synthetic private sentinel", repr(result.issues))
        self.write("profile/example.json", "{invalid")
        self.assertIn("profile_example_json", self.codes(check_repository(self.root)))

    def test_redirected_targets_are_never_read(self):
        outside = Path(self.scratch.name) / "redirect-target.md"
        outside.write_text("# Secret outside content", encoding="utf-8")
        link = self.root / "redirect.md"
        try:
            os.symlink(outside, link)
        except OSError as error:
            self.skipTest(f"Creating symlinks is unavailable: {error}")
        self.write("README.md", "[redirect](redirect.md#secret)\n")
        self.git("add", "README.md")
        original_read = Path.read_text

        def guarded_read(path, *args, **kwargs):
            self.assertNotEqual(path.resolve(), outside.resolve())
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read):
            result = check_repository(self.root)
        self.assertTrue(result.ok, result.issues)
        self.assertIn("link_redirect", self.codes(result))
        self.assertEqual(result.stats["skipped_redirects"], 1)


if __name__ == "__main__":
    unittest.main()
