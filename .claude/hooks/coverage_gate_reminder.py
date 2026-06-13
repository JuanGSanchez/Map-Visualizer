#!/usr/bin/env python3
"""PostToolUse hook — remind to run the coverage gate after a core/test edit.

Surfaces CLAUDE.md invariant: >=90% core coverage gate must be green before a change
is done, and it must NEVER be weakened. Non-blocking: this is a reminder, not an
enforcement — test-author runs and owns the gate. It also flags an attempt to weaken
the gate config in pyproject.toml.

Fires (PostToolUse) after Edit|Write. Reads the JSON on stdin; prints a reminder to
stderr (exit 0 — advisory) when a core/test file changed; escalates the message when
the pyproject gate/omit was touched. Fast: pure-stdlib, path checks only.
"""
import json
import sys

GATE_RELEVANT = ("map_visualizer/core.py", "map_visualizer/enums.py",
                 "/tests/", "tests/test_")


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ti = data.get("tool_input", {}) or {}
    path = (ti.get("file_path") or "").replace("\\", "/")

    if path.endswith("pyproject.toml"):
        new = ti.get("content") or ti.get("new_string") or ""
        if "--cov-fail-under" in new or "omit" in new:
            sys.stderr.write(
                "REMINDER (coverage gate): pyproject.toml was edited near the gate "
                "config. NEVER lower --cov-fail-under (90) or widen the coverage omit "
                "list to pass — that voids the regression contract (CLAUDE.md). "
                "Verify the gate is still --cov-fail-under=90 with gui/* and api/* "
                "the ONLY omits.\n"
            )
        return 0

    if any(k in path for k in GATE_RELEVANT):
        sys.stderr.write(
            "REMINDER (coverage gate): core/test code changed. Before calling the "
            "item done, run `python -m pytest` and confirm the >=90% core gate is "
            "green (gui/* and api/* omitted). New core code needs covering tests. "
            "A red gate = NOT done; never weaken the gate to pass.\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
