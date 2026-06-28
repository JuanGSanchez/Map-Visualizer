#!/usr/bin/env python3
"""PreToolUse hook -- block writing secrets or frozen build bundles into the repo.

Enforces CLAUDE.md invariant 8: never commit secrets (.env / keys / tokens) or built
PyInstaller bundles (packaging/bin/, packaging/work/). Blocks at the Write/Edit step so
such files never enter the working tree to be committed.

Fires on Edit|Write. Reads the PreToolUse JSON on stdin; blocks (exit 2) when the target
path is under a bundle dir or looks like a secret file, or when obvious secret material
would be written. Fast: pure-stdlib, path + light content checks only.

## Principles Applied
P1 Source-of-Truth Grounding -- the no-secrets/no-artifacts rule traces to CLAUDE.md
  invariant 8 and python-repo-conventions.md D8; no invented rule.
P2 Full Determinism -- path/content checks are deterministic; identical input -> identical exit.
P8 Principles Inheritance -- harness-level enforcement of the canonical no-secrets/no-bundles
  custom repo rule (C1 in packaging-builder; invariant 8 in CLAUDE.md).
P11 Programmatic Determinism -- this hook IS the deterministic harness; the no-secrets/no-bundles
  contract is enforced by PreToolUse before any write reaches the working tree.
"""
import json
import re
import sys

# Bundle / build-output paths that must stay OUT of VCS.
BUNDLE_DIRS = ("packaging/bin/", "packaging/work/")
# Secret-ish file targets.
SECRET_NAMES = (".env",)
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
# Obvious secret material in content (conservative — avoids false positives on code).
SECRET_CONTENT = re.compile(
    r"(?i)(?:aws_secret_access_key|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})"
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ti = data.get("tool_input", {}) or {}
    path = (ti.get("file_path") or "").replace("\\", "/")
    norm = path.lower()
    name = norm.rsplit("/", 1)[-1]

    if any(d in norm for d in BUNDLE_DIRS):
        sys.stderr.write(
            f"BLOCKED (no committed bundles): {path} is under a PyInstaller build "
            "output dir (packaging/bin/ or packaging/work/). Frozen bundles stay out "
            "of VCS — build them locally via packaging/build.py; they are gitignored. "
            "See CLAUDE.md invariant 8.\n"
        )
        return 2

    if name in SECRET_NAMES or name.endswith(SECRET_SUFFIXES):
        sys.stderr.write(
            f"BLOCKED (no secrets): {path} looks like a secret file (.env/key/cert). "
            "Never commit keys/tokens/.env. See CLAUDE.md invariant 8.\n"
        )
        return 2

    content = ti.get("content") or ti.get("new_string") or ""
    if SECRET_CONTENT.search(content):
        sys.stderr.write(
            f"BLOCKED (no secrets): secret-looking material would be written to {path}. "
            "Remove the key/token; never commit secrets. See CLAUDE.md invariant 8.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
