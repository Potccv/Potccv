import unittest

from rulecheck.markdown import github_slug, parse_markdown


class MarkdownTests(unittest.TestCase):
    def test_reference_links_images_and_inline_links(self):
        document = parse_markdown(
            "[reference][target]\n\n![picture][image]\n\n"
            "[inline](other.md#title)\n\n"
            "[target]: guide.md#中文标题\n[image]: assets/picture.png\n"
        )
        self.assertEqual([link.target for link in document.links], [
            "guide.md#%E4%B8%AD%E6%96%87%E6%A0%87%E9%A2%98", "assets/picture.png", "other.md#title"
        ])
        self.assertEqual([link.image for link in document.links], [False, True, False])
        self.assertEqual([link.line for link in document.links], [1, 3, 5])

    def test_code_examples_do_not_create_links_or_anchors(self):
        document = parse_markdown(
            "```markdown\n# Fake heading\n[bad](missing.md)\n<a id='fake'></a>\n```\n\n"
            "    [indented](missing-too.md)\n\n"
            "`[inline code](missing-three.md)`\n\n# Real heading\n"
        )
        self.assertEqual(document.links, [])
        self.assertEqual(document.anchors, {"real-heading"})

    def test_formatted_chinese_headings_and_colliding_slugs(self):
        document = parse_markdown(
            "# 中文 **标题**：`示例`\n# Repeat\n# Repeat\n# Repeat-1\n# Repeat\n"
            "# Heading ![Alt text](picture.png)\n# <span>HTML 标题</span>\n"
        )
        self.assertEqual(document.anchors, {
            "中文-标题示例", "repeat", "repeat-1", "repeat-1-1", "repeat-2",
            "heading-alt-text", "html-标题",
        })

    def test_custom_html_anchors_and_html_links(self):
        document = parse_markdown(
            "<a name='Legacy'></a>\n<div id='custom-anchor'></div>\n\n"
            "Text <span id='inline-id'></span> <a href='guide.md#Legacy'>go</a>\n"
            "<img src='asset.png'/>\n"
        )
        self.assertTrue({"Legacy", "custom-anchor", "inline-id"} <= document.anchors)
        self.assertEqual([link.target for link in document.links], ["guide.md#Legacy", "asset.png"])
        self.assertTrue(document.links[-1].image)

    def test_slug_keeps_unicode_and_hyphen_underscore(self):
        self.assertEqual(github_slug("Hello, 中文 / C++ & A_B-C! 😀"), "hello-中文--c--a_b-c-")

    def test_heading_slug_strips_visible_outer_whitespace(self):
        document = parse_markdown("# <span> Title </span>\n")
        self.assertEqual(document.anchors, {"title"})
        self.assertEqual(github_slug(" \tTitle\n "), "title")


if __name__ == "__main__":
    unittest.main()
