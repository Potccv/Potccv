"""Small shared result types; checking modules never write their inputs."""

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str = ""
    line: int | None = None
    severity: str = "error"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CheckResult:
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add(
        self,
        code: str,
        message: str,
        path: str | Path = "",
        line: int | None = None,
        severity: str = "error",
    ) -> None:
        self.issues.append(Issue(code, message, str(path), line, severity))
