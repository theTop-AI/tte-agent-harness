"""A deliberately small credential-shape scanner.

It catches the slips that matter most here (cloud keys, tokens, private keys pasted into a file or
a diff). It is not a replacement for a dedicated scanner such as gitleaks; when one is installed,
run it too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("AWS secret access key",
     re.compile(r"aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+]{40}\b", re.IGNORECASE)),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{30,}")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-)[A-Za-z0-9_\-]{30,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{20,}")),
    ("Stripe live key", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}")),
    ("Atlassian API token", re.compile(r"\bATATT3[A-Za-z0-9_\-=]{50,}")),
    ("WorkOS API key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{30,}")),
]


@dataclass
class Hit:
    where: str
    line: int
    kind: str

    def __str__(self) -> str:
        return f"{self.where}:{self.line}: looks like a {self.kind}"


def scan_text(text: str, where: str) -> list[Hit]:
    hits: list[Hit] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, pattern in PATTERNS:
            if pattern.search(line):
                hits.append(Hit(where, lineno, kind))
    return hits


def scan_files(paths: Iterable[Path], base: Path) -> list[Hit]:
    hits: list[Hit] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits.extend(scan_text(text, str(path.relative_to(base))))
    return hits


def scan_diff(diff: str) -> list[Hit]:
    """Scan only the added lines of a unified diff."""
    hits: list[Hit] = []
    current = "?"
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            current = raw[6:] if raw.startswith("+++ b/") else raw[4:]
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) - 1 if m else 0
            continue
        if raw.startswith("+"):
            lineno += 1
            for kind, pattern in PATTERNS:
                if pattern.search(raw[1:]):
                    hits.append(Hit(current, lineno, kind))
        elif not raw.startswith("-"):
            lineno += 1
    return hits
