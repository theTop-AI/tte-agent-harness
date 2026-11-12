"""Small shared helpers: YAML, hashing, paths, subprocess, findings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only on a bare interpreter
    raise SystemExit(
        "tte-harness needs PyYAML. Run it through bin/tte-harness, which finds or provisions it, "
        "or install it: Ubuntu `sudo apt-get install python3-yaml` (preinstalled on EC2 images), "
        "elsewhere `uv run --with pyyaml==6.0.2 ...`."
    ) from exc

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)


class HarnessError(Exception):
    """An error with a message meant for the person running the command."""


@dataclass
class Finding:
    level: str  # "error" | "warning"
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.path}: {self.message}"


@dataclass
class Findings:
    items: list[Finding] = field(default_factory=list)

    def error(self, path: Path | str, message: str) -> None:
        self.items.append(Finding("error", str(path), message))

    def warn(self, path: Path | str, message: str) -> None:
        self.items.append(Finding("warning", str(path), message))

    def extend(self, other: "Findings") -> None:
        self.items.extend(other.items)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.items if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.items if f.level == "warning"]

    def errors_for(self, path: Path | str) -> list[Finding]:
        return [f for f in self.errors if f.path == str(path)]


def load_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise HarnessError(f"{path}: invalid YAML: {exc}") from exc


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a Markdown file into its YAML frontmatter and body. Raises HarnessError."""
    match = FRONTMATTER_RE.match(text.replace("\r\n", "\n"))
    if not match:
        raise HarnessError("missing YAML frontmatter (the file must start with a '---' block)")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise HarnessError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise HarnessError("frontmatter must be a mapping")
    return meta, match.group(2)


def headings(markdown: str) -> list[str]:
    """Return the text of every Markdown heading, outside fenced code blocks."""
    out: list[str] = []
    fenced = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = HEADING_RE.match(line)
        if m:
            out.append(m.group(2))
    return out


def section(markdown: str, title: str) -> str | None:
    """Return the text under the heading `title` (any level) up to the next heading of the same or
    higher level, or None when there is no such heading."""
    lines = markdown.splitlines()
    fenced = False
    start = level = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        depth = len(m.group(1))
        if start is None:
            if slug(m.group(2)) == slug(title):
                start, level = i, depth
        elif depth <= level:
            return "\n".join(lines[start:i]).strip() + "\n"
    if start is None:
        return None
    return "\n".join(lines[start:]).strip() + "\n"


def slug(text: str) -> str:
    """GitHub-style heading anchor."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def expand(path: str) -> Path:
    """Expand ~ and ${VAR:-default} forms used in config files."""

    def repl(m: re.Match[str]) -> str:
        name, default = m.group(1), m.group(2) or ""
        return os.environ.get(name) or os.path.expanduser(default)

    expanded = re.sub(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}", repl, path)
    return Path(os.path.expanduser(expanded))


def home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def claude_config_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else home() / ".claude"


def codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env).expanduser() if env else home() / ".codex"


def agents_skills_dir() -> Path:
    """The shared Agent Skills folder Codex reads for user skills (and Orca installs into)."""
    return home() / ".agents" / "skills"


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    root = Path(base) if base else home() / ".local" / "state"
    return root / "tte-agent-harness"


def bin_dir() -> Path:
    return home() / ".local" / "bin"


def run(cmd: list[str], cwd: Path | None = None, timeout: float | None = 60,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=env,
                          check=False)


def git(args: list[str], cwd: Path) -> str | None:
    """Run git and return stripped stdout, or None when git fails."""
    try:
        proc = run(["git", *args], cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def iter_files(root: Path) -> Iterable[Path]:
    """Every regular file under root, sorted, skipping caches and symlinks."""
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts):
            continue
        yield path
