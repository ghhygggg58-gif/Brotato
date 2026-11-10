#!/usr/bin/env python3
"""Easy one-file downloader & setup script for Brotato Python.

Downloads the game's Python folder directly from GitHub (works for both public
and private repos via GITHUB_TOKEN / GH_TOKEN or `gh` CLI), extracts a clean
playable folder, installs runtime dependencies into a local `.venv`, and can
launch the game immediately.

Zero third-party dependencies are required to run this script (stdlib only).
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO_OWNER = "ghhygggg58-gif"
REPO_NAME = "Brotato"
DEFAULT_BRANCH = "main"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "screenshots",
    "saves",
}

EXCLUDE_EXTS = {".pyc", ".pyo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and set up the Brotato Python game folder."
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("Brotato-Python"),
        help="Destination folder to create (default: ./Brotato-Python)",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=f"GitHub branch or tag to download (default: {DEFAULT_BRANCH})",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "",
        help="Optional GitHub token (needed if repository is private)",
    )
    parser.add_argument(
        "--zip-only",
        action="store_true",
        help="Only save the clean game archive (<dest>.zip) without extracting or installing",
    )
    parser.add_argument(
        "--no-venv",
        action="store_true",
        help="Extract the game folder without creating .venv or installing packages",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Launch the game immediately after setup completes",
    )
    parser.add_argument(
        "--local-repo",
        type=Path,
        default=None,
        help="Copy/package from a local repo directory instead of downloading from GitHub",
    )
    parser.add_argument(
        "--shortcut",
        action="store_true",
        help="Create Linux Mint / XDG Desktop and Application Menu shortcuts",
    )
    parser.add_argument(
        "--fix-linux-deps",
        action="store_true",
        help="On Debian/Ubuntu/Linux Mint, automatically run sudo apt-get install python3-venv if venv is missing",
    )
    return parser.parse_args()


def _download_github_zip(branch: str, token: str) -> bytes:
    urls = [
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/zipball/{branch}",
        f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{branch}.zip",
    ]

    last_err: Exception | None = None
    for url in urls:
        headers = {"User-Agent": "brotato-python-downloader/1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (401, 403, 404):
                continue
            raise
        except Exception as exc:
            last_err = exc

    # Fallback: try GitHub CLI (`gh`) if installed & authenticated (great for private repos)
    gh_exe = shutil.which("gh")
    if gh_exe:
        try:
            res = subprocess.run(
                [gh_exe, "api", f"repos/{REPO_OWNER}/{REPO_NAME}/zipball/{branch}"],
                capture_output=True,
                check=True,
                timeout=60,
            )
            if res.stdout:
                return res.stdout
        except Exception as exc:
            last_err = exc

    raise RuntimeError(
        f"Could not download {REPO_OWNER}/{REPO_NAME} ({branch}) from GitHub. "
        f"If the repository is private, pass --token <TOKEN> or authenticate with `gh auth login`. "
        f"Last error: {last_err}"
    )


def _should_skip_relpath(rel_parts: tuple[str, ...]) -> bool:
    if not rel_parts:
        return True
    if any(part in EXCLUDE_DIRS for part in rel_parts):
        return True
    if Path(rel_parts[-1]).suffix in EXCLUDE_EXTS:
        return True
    return False


def _zip_from_local_repo(local_repo: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(local_repo.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(local_repo)
            if _should_skip_relpath(rel.parts):
                continue
            zf.write(path, arcname=f"Brotato-local/{rel.as_posix()}")
    return buf.getvalue()


def _extract_clean_game_folder(zip_bytes: bytes, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = Path(info.filename).parts
            # Strip GitHub's top-level "<repo>-<branch-or-sha>/" wrapper folder
            rel_parts = parts[1:] if len(parts) > 1 else parts
            if _should_skip_relpath(rel_parts):
                continue
            out_path = dest.joinpath(*rel_parts)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, out_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            # Preserve executable bit for shell/command scripts on Unix
            if out_path.suffix in (".sh", ".command") and os.name != "nt":
                os.chmod(out_path, 0o755)
            count += 1
    return count


def _write_clean_zip(zip_bytes: bytes, zip_out: Path) -> int:
    zip_out.parent.mkdir(parents=True, exist_ok=True)
    folder_name = zip_out.stem
    count = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as src_zf, zipfile.ZipFile(
        zip_out, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst_zf:
        for info in src_zf.infolist():
            if info.is_dir():
                continue
            parts = Path(info.filename).parts
            rel_parts = parts[1:] if len(parts) > 1 else parts
            if _should_skip_relpath(rel_parts):
                continue
            arc = f"{folder_name}/{'/'.join(rel_parts)}"
            dst_zf.writestr(arc, src_zf.read(info.filename))
            count += 1
    return count


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _setup_venv(dest: Path, fix_linux_deps: bool = False) -> Path:
    venv_dir = dest / ".venv"
    py_exe = _venv_python(venv_dir)
    if not py_exe.exists():
        check = subprocess.run(
            [sys.executable, "-c", "import ensurepip, venv"],
            capture_output=True,
        )
        if check.returncode != 0:
            if os.name != "nt" and shutil.which("apt-get"):
                if fix_linux_deps:
                    print("Installing missing python3-venv & python3-pip via apt...")
                    subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)
                    subprocess.run(["sudo", "apt-get", "install", "-y", "python3-venv", "python3-pip"], check=True)
                else:
                    raise RuntimeError(
                        "Python's `venv` module is not installed (common on fresh Linux Mint / Ubuntu).\n"
                        "Run this once and re-run:\n"
                        "  sudo apt update && sudo apt install -y python3-venv python3-pip\n"
                        "Or pass --fix-linux-deps (or use install_linux.sh)."
                    )
        print(f"Creating virtual environment in {venv_dir} ...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    print("Installing runtime dependencies (pygame-ce, numpy) ...")
    subprocess.run(
        [str(py_exe), "-m", "pip", "install", "--upgrade", "pygame-ce>=2.5.0", "numpy>=1.26.0"],
        check=True,
    )
    return py_exe


def main() -> int:
    args = parse_args()

    if args.local_repo is not None:
        local_path = args.local_repo.resolve()
        if not (local_path / "main.py").is_file():
            print(f"Error: {local_path} does not contain main.py", file=sys.stderr)
            return 1
        print(f"Packaging local repository from {local_path} ...")
        raw_zip = _zip_from_local_repo(local_path)
    else:
        print(f"Downloading {REPO_OWNER}/{REPO_NAME} ({args.branch}) ...")
        raw_zip = _download_github_zip(args.branch, args.token)

    if args.zip_only:
        zip_out = args.dest.with_suffix(".zip")
        n_files = _write_clean_zip(raw_zip, zip_out)
        print(f"Saved {zip_out.resolve()} ({n_files} files).")
        return 0

    dest = args.dest.resolve()
    n_files = _extract_clean_game_folder(raw_zip, dest)
    print(f"Extracted {n_files} files into {dest}")

    py_exe = Path(sys.executable)
    if not args.no_venv:
        py_exe = _setup_venv(dest, fix_linux_deps=args.fix_linux_deps)

    if args.shortcut and os.name != "nt":
        shortcut_script = dest / "scripts" / "create_linux_shortcut.py"
        if shortcut_script.is_file():
            subprocess.run([str(py_exe), str(shortcut_script), "--game-dir", str(dest)], check=False)

    print("\nSetup complete!")
    print(f"Game folder: {dest}")
    if os.name == "nt":
        print(f"Play anytime by double-clicking: {dest / 'Play_Brotato.bat'}")
    else:
        print(f"Play anytime with: cd \"{dest}\" && ./play_brotato.sh")

    if args.run:
        print("Launching Brotato Python ...")
        subprocess.run([str(py_exe), str(dest / "main.py")], cwd=str(dest), check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
