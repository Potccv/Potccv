"""Extract actual Markdown links and GitHub-style anchors with markdown-it-py."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import unicodedata

from markdown_it import MarkdownIt


@dataclass(frozen=True)
class MarkdownLink:
    target: str
    line: int
    image: bool = False


@dataclass
class MarkdownDocument:
    links: list[MarkdownLink] = field(default_factory=list)
    anchors: set[str] = field(default_factory=set)


def github_slug(text: str) -> str:
    """Keep Unicode letters/marks and GitHub's hyphen/underscore exceptions."""
    lowered = text.strip().lower()
    return "".join(
        char for char in lowered
        if char in "-_ " or unicodedata.category(char)[0] not in "PSCZ"
    ).replace(" ", "-")


class _HTMLReferences(HTMLParser):
    def __init__(self, document: MarkdownDocument, line: int):
        super().__init__(convert_charrefs=True)
        self.document = document
        self.line = line

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for anchor in (values.get("id"), values.get("name") if tag == "a" else None):
            if anchor:
                self.document.anchors.add(anchor)
        attribute = "href" if tag == "a" else "src" if tag == "img" else None
        if attribute and values.get(attribute) is not None:
            self.document.links.append(MarkdownLink(
                values[attribute], self.line + self.getpos()[0] - 1, tag == "img"
            ))

    handle_startendtag = handle_starttag


def _visible_text(tokens) -> str:
    pieces = []
    for token in tokens or []:
        if token.type in {"text", "code_inline"}:
            pieces.append(token.content)
        elif token.type == "image":
            pieces.append(_visible_text(token.children) or token.content)
        elif token.type in {"softbreak", "hardbreak"}:
            pieces.append(" ")
    return "".join(pieces)


def parse_markdown(text: str) -> MarkdownDocument:
    """Ignore code blocks/examples; resolve reference links through the parser."""
    document = MarkdownDocument()
    tokens = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"]).parse(text)
    heading_slugs: set[str] = set()
    for index, token in enumerate(tokens):
        line = token.map[0] + 1 if token.map else 1
        if token.type == "heading_open" and index + 1 < len(tokens):
            base = github_slug(_visible_text(tokens[index + 1].children))
            slug = base
            suffix = 0
            while slug in heading_slugs:
                suffix += 1
                slug = f"{base}-{suffix}"
            heading_slugs.add(slug)
            document.anchors.add(slug)
        if token.type == "html_block":
            _HTMLReferences(document, line).feed(token.content)
        if token.type != "inline":
            continue
        current_line = line
        for child in token.children or []:
            if child.type == "link_open":
                document.links.append(MarkdownLink(child.attrGet("href") or "", current_line))
            elif child.type == "image":
                document.links.append(MarkdownLink(child.attrGet("src") or "", current_line, True))
            elif child.type == "html_inline":
                _HTMLReferences(document, current_line).feed(child.content)
            if child.type in {"softbreak", "hardbreak"}:
                current_line += 1
    return document
