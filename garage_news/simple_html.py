"""Lightweight HTML parsing helpers used by the scraper.

This is a very small wrapper over :class:`html.parser.HTMLParser` that provides
just enough of the BeautifulSoup API for the scraper's needs.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Iterable, Optional


class Node:
    def __init__(self, name: str, attrs: dict[str, str], parent: Optional["Node"] = None) -> None:
        self.name = name.lower()
        self.attrs = {k.lower(): v for k, v in attrs.items()}
        self.parent = parent
        self.children: list[Node] = []
        self.text_chunks: list[str] = []

    # Metadata helpers -----------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self.attrs.get(key.lower(), default)

    def __getitem__(self, key: str) -> Any:
        return self.attrs[key.lower()]

    @property
    def string(self) -> str:
        return self.get_text(strip=True)

    # Tree navigation ------------------------------------------------------
    def _iter_descendants(self) -> Iterable["Node"]:
        for child in self.children:
            yield child
            yield from child._iter_descendants()

    # Search ---------------------------------------------------------------
    def _matches_attr(self, key: str, expected: Any) -> bool:
        if expected is None:
            return True
        actual = self.attrs.get(key.lower())
        if expected is True:
            return actual is not None
        if actual is None:
            return False
        if isinstance(expected, re.Pattern):
            return bool(expected.search(actual))
        return str(actual) == str(expected)

    def _matches(self, name: Optional[str], class_: Any, attrs: dict[str, Any]) -> bool:
        if name and self.name != name.lower():
            return False
        if not self._matches_attr("class", class_):
            return False
        for key, expected in attrs.items():
            if not self._matches_attr(key, expected):
                return False
        return True

    def find_all(self, name: Optional[str] = None, class_: Any = None, **attrs: Any) -> list["Node"]:
        matches: list[Node] = []
        for node in self._iter_descendants():
            if node._matches(name, class_, attrs):
                matches.append(node)
        return matches

    def find(self, name: Optional[str] = None, class_: Any = None, **attrs: Any) -> Optional["Node"]:
        for node in self._iter_descendants():
            if node._matches(name, class_, attrs):
                return node
        return None

    # Text extraction ------------------------------------------------------
    def get_text(self, separator: str = " ", strip: bool = False) -> str:
        pieces: list[str] = []

        def walk(node: "Node") -> None:
            if node.text_chunks:
                pieces.append("".join(node.text_chunks))
            for child in node.children:
                walk(child)

        walk(self)
        text = separator.join(part for part in pieces if part)
        return text.strip() if strip else text

    # Mutation -------------------------------------------------------------
    def append_child(self, node: "Node") -> None:
        self.children.append(node)

    def append_text(self, text: str) -> None:
        self.text_chunks.append(text)


class _SoupParser(HTMLParser):
    def __init__(self, root: Node):
        super().__init__(convert_charrefs=True)
        self.stack = [root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        parent = self.stack[-1]
        node = Node(tag, dict(attrs), parent=parent)
        parent.append_child(node)
        self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        parent = self.stack[-1]
        node = Node(tag, dict(attrs), parent=parent)
        parent.append_child(node)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        while len(self.stack) > 1:
            node = self.stack.pop()
            if node.name == tag_lower:
                break

    def handle_data(self, data: str) -> None:
        if not self.stack:
            return
        self.stack[-1].append_text(data)


class BeautifulSoup(Node):  # pragma: no cover - thin wrapper tested via scraper
    def __init__(self, html: str) -> None:
        super().__init__("[document]", {})
        parser = _SoupParser(self)
        parser.feed(html)

    @property
    def title(self) -> Optional[Node]:
        return self.find("title")

    @property
    def body(self) -> Optional[Node]:
        return self.find("body")
