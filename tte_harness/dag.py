"""Dependency graphs: cycle detection and parallel waves (Kahn's algorithm)."""

from __future__ import annotations

from typing import Mapping, Sequence


def find_cycle(deps: Mapping[str, Sequence[str]]) -> list[str] | None:
    """Return one cycle as a list of node ids (first id repeated at the end), or None.

    `deps` maps each node to the nodes it depends on. Unknown dependency ids are ignored here;
    the caller reports them separately.
    """
    white, grey, black = 0, 1, 2
    color = {n: white for n in deps}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = grey
        stack.append(node)
        for dep in deps.get(node, ()):
            if dep not in color:
                continue
            if color[dep] == grey:
                return stack[stack.index(dep):] + [dep]
            if color[dep] == white:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        color[node] = black
        return None

    for node in sorted(deps):
        if color[node] == white:
            found = visit(node)
            if found:
                return found
    return None


def waves(deps: Mapping[str, Sequence[str]]) -> list[list[str]]:
    """Group nodes into waves: every node's dependencies sit in earlier waves, so the nodes of one
    wave can run in parallel. Raises ValueError on a cycle or an unknown dependency."""
    for node, ds in deps.items():
        for d in ds:
            if d not in deps:
                raise ValueError(f"{node} depends on unknown {d}")
    cycle = find_cycle(deps)
    if cycle:
        raise ValueError("dependency cycle: " + " -> ".join(cycle))
    remaining = {n: set(ds) for n, ds in deps.items()}
    done: set[str] = set()
    out: list[list[str]] = []
    while remaining:
        wave = sorted(n for n, ds in remaining.items() if ds <= done)
        out.append(wave)
        for n in wave:
            del remaining[n]
        done.update(wave)
    return out


def topological(deps: Mapping[str, Sequence[str]]) -> list[str]:
    return [n for wave in waves(deps) for n in wave]
