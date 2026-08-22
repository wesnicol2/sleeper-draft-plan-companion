#!/usr/bin/env python3
"""One-shot rename of this template into a real project.

Run by .github/workflows/template-bootstrap.yml on the first push to main in a
repo created from the template. Takes the repo's full name (``owner/repo``) and
rewrites every place the template's own name is baked in, then renames the
``app`` package to match.

Deliberately touches **no file under .github/workflows/**: pushes made with the
Actions ``GITHUB_TOKEN`` are refused for workflow files, so the workflows are
written to derive everything they need from ``${{ github.repository }}``.

Every substitution asserts that it actually matched. A silent no-op here would
leave a half-renamed repo that still builds, which is the worst outcome.
"""

from __future__ import annotations

import keyword
import re
import subprocess
import sys
from pathlib import Path

TEMPLATE_OWNER_REPO = "wesnicol2/python-service-template"
TEMPLATE_NAME = "python-service-template"
TEMPLATE_PKG = "app"

ROOT = Path(__file__).resolve().parent.parent


def package_name(project: str) -> str:
    """Turn a repo name into an importable package name.

    Prefixes rather than suffixes when the raw name is unusable: a repo called
    ``2fast`` needs ``app_2fast``, since ``2fast_app`` still starts with a digit.
    """
    pkg = re.sub(r"[^0-9a-zA-Z_]+", "_", project.lower()).strip("_")
    if not pkg:
        return "app"
    if pkg[0].isdigit() or keyword.iskeyword(pkg) or not pkg.isidentifier():
        pkg = f"app_{pkg}"
    return pkg


def rewrite(rel_path: str, pairs: list[tuple[str, str]]) -> None:
    """Apply ordered replacements to one file, failing loudly on a no-op."""
    path = ROOT / rel_path
    text = original = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old == new:
            continue
        if old not in text:
            raise SystemExit(f"bootstrap: expected {old!r} in {rel_path}, template has drifted")
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"  rewrote {rel_path}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: bootstrap.py <owner/repo>", file=sys.stderr)
        return 2

    full_name = argv[1]
    project = full_name.split("/")[-1]
    pkg = package_name(project)

    print(f"bootstrap: {full_name}  project={project}  package={pkg}")

    # Longest/most-qualified strings first: replacing the bare template name
    # before the owner-qualified one would corrupt the image references.
    rewrite(
        "README.md",
        [
            (f"ghcr.io/{TEMPLATE_OWNER_REPO}", f"ghcr.io/{full_name}"),
            (f"python -m {TEMPLATE_PKG}.api", f"python -m {pkg}.api"),
            (f"`{TEMPLATE_PKG}/api.py`", f"`{pkg}/api.py`"),
            (f"- `{TEMPLATE_PKG}/`", f"- `{pkg}/`"),
            (TEMPLATE_NAME, project),
        ],
    )
    rewrite(
        "docker-compose.yml",
        [
            (f"ghcr.io/{TEMPLATE_OWNER_REPO}", f"ghcr.io/{full_name}"),
            (f"\n  {TEMPLATE_PKG}-test:\n", f"\n  {project}-test:\n"),
            (f"\n  {TEMPLATE_PKG}:\n", f"\n  {project}:\n"),
        ],
    )
    rewrite("pyproject.toml", [(f'name = "{TEMPLATE_NAME}"', f'name = "{project}"')])
    rewrite("pyproject.toml", [(f'packages = ["{TEMPLATE_PKG}"]', f'packages = ["{pkg}"]')])
    rewrite("Dockerfile", [(f'"-m", "{TEMPLATE_PKG}.api"', f'"-m", "{pkg}.api"')])
    rewrite("tests/test_api.py", [(f"from {TEMPLATE_PKG}.api", f"from {pkg}.api")])
    rewrite(
        f"{TEMPLATE_PKG}/api.py",
        [(f"python -m {TEMPLATE_PKG}.api", f"python -m {pkg}.api")],
    )
    rewrite(
        f"{TEMPLATE_PKG}/__init__.py",
        [
            (
                "Renamed to match the repository by the bootstrap step.",
                f"Entrypoint is {pkg}.api.",
            )
        ],
    )

    if pkg != TEMPLATE_PKG:
        subprocess.run(["git", "mv", TEMPLATE_PKG, pkg], cwd=ROOT, check=True)
        print(f"  renamed {TEMPLATE_PKG}/ -> {pkg}/")

    (ROOT / ".template-bootstrapped").write_text(f"{full_name}\n", encoding="utf-8")
    print("  wrote .template-bootstrapped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
