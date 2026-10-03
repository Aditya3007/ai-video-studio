#!/usr/bin/env bash
# package_project.sh -- create a clean, transfer-safe ZIP of the AI Video Studio project.
#
# Usage:
#   ./scripts/package_project.sh
#   ./scripts/package_project.sh /path/to/output
#   ./scripts/package_project.sh --dry-run
#   ./scripts/package_project.sh --validate path/to/archive.zip
#
# The script works from any working directory: it discovers the repository root from
# the location of this script, then packages everything required to continue
# development on another machine while excluding dependencies, caches, build
# artifacts, secrets, local databases, and other machine-specific files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export REPO_ROOT

if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 is required" >&2
    exit 1
fi

python3 - "$@" <<'PY'
import argparse
import fnmatch
import os
import stat
import sys
import zipfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = os.environ["REPO_ROOT"]
ARCHIVE_PREFIX = "AI_Video_Studio"

# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------
# Categories are reported to the user. Reason strings are shown in dry-run mode.


def dir_exclusion(rel: str, name: str):
    """Return (category, reason) if a directory should be pruned, else None."""
    candidate = name if rel == "." else f"{rel}/{name}"

    # Local/runtime storage directories (anchored paths; do NOT match app/storage source)
    if candidate == "storage" or candidate == "backend/storage":
        return ("local storage/runtime data", "local filesystem object storage")
    if candidate == ".devin":
        return ("local devin config", "machine-specific Devin settings")
    if candidate == ".git":
        return ("git history", "Git repository metadata")
    if name.endswith(".egg-info") or candidate == "backend/ai_video_studio_backend.egg-info":
        return ("python build metadata", "setuptools egg-info")

    # Python virtual environments and tool caches
    if name in {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}:
        return ("python cache", f"{name} cache directory")
    if name in {".venv", "venv", "env", "ENV"}:
        return ("python virtual environment", f"{name} directory")
    if name in {".tox", ".nox", ".hypothesis", ".pyre", ".pytype", ".eggs"}:
        return ("python tool/build artifacts", f"{name} directory")
    if name in {".Python", ".python", "lib", "lib64", "bin", "include",
                "develop-eggs", "eggs", "parts", "sdist", "var", "wheels"}:
        return ("python build/venv internals", f"{name} directory")

    # Node/npm artifacts
    if name == "node_modules":
        return ("node dependencies", "npm package tree")
    if name == ".pnpm-store":
        return ("node cache", "pnpm store")

    # Frontend build/cache artifacts
    if rel == "frontend" or rel.startswith("frontend/"):
        if name in {"dist", "build", ".vite", "coverage"}:
            return ("frontend build artifacts", f"frontend {name} directory")

    # Test/coverage reports
    if name in {"coverage", "htmlcov"}:
        return ("coverage reports", f"{name} directory")

    # Temporary and local data directories
    if name in {"tmp", "temp", "cache", "caches", "logs", "secrets", "generated"}:
        return ("temporary/local data", f"{name} directory")

    # IDE/OS directories
    if name in {".vscode", ".idea"}:
        return ("ide/os metadata", f"{name} directory")

    return None


def file_exclusion(rel: str, name: str):
    """Return (category, reason) if a file should be skipped, else None."""
    candidate = name if rel == "." else f"{rel}/{name}"

    # Avoid packing previously generated transfer archives when they sit in the repo root
    if rel == "." and name.startswith("AI_Video_Studio_") and name.endswith(".zip"):
        return ("packaging output", "generated transfer archive")

    # Machine-specific local config files
    if candidate == ".devin/config.local.json":
        return ("local devin config", "machine-specific Devin local config")
    if candidate in {"backend/alembic_dev.db", "backend/migration_temp.db"}:
        return ("local database", "local SQLite migration database")

    # Environment / secrets
    if name.startswith(".env"):
        if name in {".env.example", ".env.template"} or name.endswith(".example") or name.endswith(".template"):
            return None
        return ("secrets", "environment file with potential secrets")
    if name.endswith(".pem") or name.endswith(".key"):
        return ("secrets", "private key/credential file")

    # Python compiled and cache artifacts
    if name.endswith(".pyc") or name.endswith(".pyo") or name == "$py.class":
        return ("python cache", "compiled Python bytecode")
    if name.endswith(".so") or name.endswith(".dylib"):
        return ("python/native build artifacts", "shared library")
    if name.endswith(".egg"):
        return ("python build metadata", "egg distribution")
    if name in {"MANIFEST", ".installed.cfg", "pyvenv.cfg"} or name.endswith(".manifest") or name.endswith(".spec"):
        return ("python build artifacts", "build/packaging file")

    # Local databases
    if name.endswith(".db") or name.endswith(".sqlite") or name.endswith(".sqlite3"):
        return ("local database", "SQLite/database file")

    # Logs and temp files
    if name.endswith(".log") or name.endswith(".tmp"):
        return ("logs/temporary", "log or temp file")
    if name.startswith("npm-debug.log") or name.startswith("yarn-debug.log") or \
       name.startswith("yarn-error.log") or name.startswith("pnpm-debug.log") or \
       name.startswith("lerna-debug.log"):
        return ("logs", "npm/yarn/pnpm debug log")

    # Test/coverage/IDE files
    if name in {".coverage", ".dmypy.json", "dmypy.json", ".DS_Store", "Thumbs.db"}:
        return ("coverage/ide artifacts", f"{name}")
    if name.endswith(".swp") or name.endswith(".swo") or name.endswith("~"):
        return ("editor artifacts", "editor swap/backup file")

    return None


def is_output_zip(candidate: str, output_rel: str | None) -> bool:
    if output_rel is None:
        return False
    return candidate == output_rel or candidate.startswith(output_rel + "/")


def human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def enumerate_files(repo_root: str, output_rel: str | None):
    """Walk the repo, returning (included_paths, excluded_summary)."""
    included = []
    excluded = {}  # category -> count
    excluded_reasons = {}  # category -> list of examples

    for dirpath, dirnames, filenames in os.walk(repo_root, topdown=True):
        # Determine the repo-relative path for this directory
        rel = os.path.relpath(dirpath, repo_root)
        if rel.startswith(".."):
            continue
        if rel == ".":
            rel = "."

        # Prune excluded directories
        kept = []
        for d in dirnames:
            cat = dir_exclusion(rel, d)
            if cat:
                category, reason = cat
                excluded[category] = excluded.get(category, 0) + 1
                if len(excluded_reasons.get(category, [])) < 5:
                    examples = excluded_reasons.setdefault(category, [])
                    examples.append(f"{rel}/{d}" if rel != "." else d)
                continue
            kept.append(d)
        dirnames[:] = kept

        for filename in filenames:
            full = os.path.join(dirpath, filename)
            # Never follow symlinks or allow files outside the repo
            if os.path.islink(full):
                excluded.setdefault("symlinks", 0)
                excluded["symlinks"] += 1
                continue
            real = os.path.realpath(full)
            if not real.startswith(repo_root + os.sep):
                excluded.setdefault("outside repo", 0)
                excluded["outside repo"] += 1
                continue

            rel_file = filename if rel == "." else f"{rel}/{filename}"

            # Exclude the archive being produced if it lives inside the repo
            if is_output_zip(rel_file, output_rel):
                continue

            cat = file_exclusion(rel, filename)
            if cat:
                category, reason = cat
                excluded[category] = excluded.get(category, 0) + 1
                if len(excluded_reasons.get(category, [])) < 5:
                    examples = excluded_reasons.setdefault(category, [])
                    examples.append(rel_file)
                continue

            included.append(full)

    return included, excluded, excluded_reasons


def build_archive(zip_path: str, included_files: list[str], repo_root: str) -> int:
    """Create the transfer ZIP and return the number of files stored."""
    written = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full in included_files:
            rel = os.path.relpath(full, repo_root)
            arcname = f"{ARCHIVE_PREFIX}/{rel}"
            zinfo = zipfile.ZipInfo.from_file(full, arcname)
            # Preserve Unix permissions (important for executable scripts)
            st = os.stat(full)
            zinfo.external_attr = (st.st_mode & 0o7777) << 16
            with open(full, "rb") as fh:
                zf.writestr(zinfo, fh.read())
            written += 1
    return written


def validate_archive(zip_path: str) -> bool:
    """Verify the archive does not contain forbidden artifacts and has key files."""
    forbidden_dir_parts = {
        ".git", ".venv", "venv", "env", "ENV", "node_modules", "__pycache__",
        "dist", "build", ".vite", "coverage", ".pytest_cache", ".ruff_cache",
        ".mypy_cache", ".tox", ".nox", ".hypothesis", ".pyre", ".pytype",
        ".eggs", ".pnpm-store", "htmlcov", "generated", "tmp", "temp",
        "cache", "caches", "logs", "secrets", ".vscode", ".idea", ".devin",
    }
    forbidden_file_suffixes = (
        ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".tmp",
        ".pem", ".key", ".so", ".dylib", ".egg", ".coverage", ".DS_Store",
    )
    forbidden_file_names = {"Thumbs.db", ".installed.cfg", "pyvenv.cfg"}

    found = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        for name in names:
            parts = name.split("/")
            basename = parts[-1]

            # Directory-level forbidden parts
            for part in parts:
                if part in forbidden_dir_parts:
                    found.append((name, f"forbidden directory component: {part}"))
                    break

            # File-level forbidden extensions
            if any(basename.endswith(suffix) for suffix in forbidden_file_suffixes):
                found.append((name, "forbidden file suffix"))
            if basename in forbidden_file_names:
                found.append((name, "forbidden file name"))

            # Real environment files (not .env.example / .env.template / *.*example/template)
            if basename.startswith(".env"):
                if not (basename in {".env.example", ".env.template"} or basename.endswith(".example") or basename.endswith(".template")):
                    found.append((name, "potential secret environment file"))

    if found:
        print("\nValidation FAILED: forbidden artifacts detected in the archive:")
        for name, reason in found:
            print(f"  - {name} ({reason})")
        return False

    # Required files/prefixes
    required_prefixes = [
        f"{ARCHIVE_PREFIX}/backend/pyproject.toml",
        f"{ARCHIVE_PREFIX}/backend/alembic/versions/",
        f"{ARCHIVE_PREFIX}/backend/app/main.py",
        f"{ARCHIVE_PREFIX}/backend/tests/",
        f"{ARCHIVE_PREFIX}/frontend/package.json",
        f"{ARCHIVE_PREFIX}/frontend/package-lock.json",
        f"{ARCHIVE_PREFIX}/frontend/src/",
        f"{ARCHIVE_PREFIX}/.env.example",
        f"{ARCHIVE_PREFIX}/README.md",
        f"{ARCHIVE_PREFIX}/CONTRIBUTING.md",
        f"{ARCHIVE_PREFIX}/ARCHITECTURE.md",
        f"{ARCHIVE_PREFIX}/ROADMAP.yaml",
        f"{ARCHIVE_PREFIX}/PROJECT_STATUS.yaml",
        f"{ARCHIVE_PREFIX}/.gitignore",
        f"{ARCHIVE_PREFIX}/.github/workflows/ci.yml",
        f"{ARCHIVE_PREFIX}/backend/alembic.ini",
    ]
    missing = [p for p in required_prefixes if not any(n.startswith(p) for n in names)]

    if missing:
        print("\nValidation warnings: expected entries not found:")
        for p in missing:
            print(f"  - {p}")
        # Missing expected files are reported but not treated as a packaging safety failure.
    else:
        print("\nRequired source/configuration entries detected.")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Package the AI Video Studio project for transfer to another machine."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be included/excluded without creating a ZIP")
    parser.add_argument("--validate", metavar="ZIP", nargs="?", const=None,
                        help="Validate an existing archive instead of creating one")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output directory or .zip path (default: repository root)")
    args = parser.parse_args()

    repo_root = REPO_ROOT

    if args.validate:
        zip_path = os.path.abspath(args.validate)
        if not os.path.isfile(zip_path):
            print(f"error: archive not found: {zip_path}", file=sys.stderr)
            sys.exit(1)
        ok = validate_archive(zip_path)
        sys.exit(0 if ok else 1)

    # Determine output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_name = f"{ARCHIVE_PREFIX}_{timestamp}.zip"
    if args.output:
        out = os.path.abspath(args.output)
        if os.path.isdir(out) or out.endswith("/"):
            out = os.path.join(out, default_name)
        elif not out.endswith(".zip"):
            os.makedirs(out, exist_ok=True) if not os.path.exists(out) else None
            out = os.path.join(out, default_name)
    else:
        out = os.path.join(repo_root, default_name)

    output_rel = None
    real_out = os.path.realpath(out)
    if real_out.startswith(os.path.realpath(repo_root) + os.sep):
        output_rel = os.path.relpath(real_out, repo_root)

    included, excluded, reasons = enumerate_files(repo_root, output_rel)

    if args.dry_run:
        print("DRY RUN - no archive will be created\n")
        print(f"Repository root: {repo_root}")
        print(f"Proposed archive: {out}")
        print(f"Files that would be included: {len(included)}")
        top_dirs = sorted({os.path.relpath(f, repo_root).split("/", 1)[0] for f in included})
        print(f"Top-level entries: {', '.join(top_dirs)}")
        print("\nSample of included files:")
        for f in sorted(included)[:30]:
            print(f"  + {os.path.relpath(f, repo_root)}")
        if len(included) > 30:
            print(f"  ... and {len(included) - 30} more")
        print("\nExcluded categories:")
        for cat, count in sorted(excluded.items(), key=lambda x: -x[1]):
            examples = reasons.get(cat, [])
            example_str = f" (e.g. {', '.join(examples)})" if examples else ""
            print(f"  - {cat}: {count}{example_str}")
        return

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    written = build_archive(out, included, repo_root)
    size = os.path.getsize(out)

    top_dirs = sorted({os.path.relpath(f, repo_root).split("/", 1)[0] for f in included})
    print(f"Archive created: {out}")
    print(f"Size: {human_size(size)}")
    print(f"Files archived: {written}")
    print(f"Top-level directories: {', '.join(top_dirs)}")
    print("\nExcluded categories:")
    for cat, count in sorted(excluded.items(), key=lambda x: -x[1]):
        examples = reasons.get(cat, [])
        example_str = f" (e.g. {', '.join(examples)})" if examples else ""
        print(f"  - {cat}: {count}{example_str}")

    ok = validate_archive(out)
    if not ok:
        print("\nThe archive was created but failed validation. It is not safe to transfer.")
        sys.exit(1)
    print("\nValidation passed: no forbidden artifacts detected.")


if __name__ == "__main__":
    main()
PY

exit $?
