#!/usr/bin/env python3
import subprocess
import sys


PROTECTED_PREFIXES = (
    ".agents/skills/",
    ".agents\\skills\\",
)


def git_status_porcelain() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def changed_path(status_line: str) -> str:
    path = status_line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path


def main() -> int:
    violations = [
        line
        for line in git_status_porcelain()
        if changed_path(line).startswith(PROTECTED_PREFIXES)
    ]

    if violations:
        print("Project constraint violation: do not modify files under .agents/skills/.", file=sys.stderr)
        for line in violations:
            print(line, file=sys.stderr)
        return 1

    print("Project constraint check passed: .agents/skills/ is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
