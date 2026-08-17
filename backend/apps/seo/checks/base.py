"""Check registry and shared types.

Each check is a pure function of ``CheckContext`` returning a ``CheckResult``,
so they are trivially unit-testable and can run against an unsaved draft --
which is what makes the editor's live SEO score honest rather than one-save
stale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"


@dataclass
class CheckContext:
    article: object
    seo: object  # ResolvedSEO
    plain_text: str
    annotations: list = field(default_factory=list)
    site: object = None


@dataclass
class CheckResult:
    id: str
    label: str
    status: str
    weight: int
    detail: str = ""
    # Where in the document the problem is, so the editor can jump to it.
    anchors: list = field(default_factory=list)

    @property
    def earned(self) -> float:
        if self.status == STATUS_OK:
            return float(self.weight)
        if self.status == STATUS_WARN:
            return self.weight * 0.5
        return 0.0


REGISTRY: list[Callable[[CheckContext], CheckResult]] = []


def register(func):
    REGISTRY.append(func)
    return func


def word_list(text: str) -> list[str]:
    return [w for w in (text or "").lower().split() if w]
