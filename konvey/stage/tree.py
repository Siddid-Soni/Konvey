"""The parsed beat tree: nodes and the one error every stage layer raises (pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field


class BeatError(ValueError):
    pass


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    # Leaves: text as (string, emphasised) segments; tex keeps its raw source.
    segments: list[tuple[str, bool]] = field(default_factory=list)

    @property
    def id(self) -> str | None:
        return self.attrs.get("id")

    @property
    def text(self) -> str:
        return " ".join("".join(s for s, _ in self.segments).split(" ")).strip()

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()
