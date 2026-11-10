"""Tests for easy download script, zip packager, and launchers."""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_download_script_extracts_clean_game_folder(tmp_path: Path) -> None:
    dest = tmp_path / "Brotato-Game"
    res = subprocess.run(
        [
            sys.executable,
            str(ROOT / "download_brotato.py"),
            "--local-repo",
            str(ROOT),
            "--dest",
            str(dest),
            "--no-venv",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Setup complete!" in res.stdout
    assert (dest / "main.py").is_file()
    assert (dest / "Play_Brotato.bat").is_file()
    assert (dest / "play_brotato.sh").is_file()
    assert (dest / "Play_Brotato.command").is_file()
    assert (dest / "data" / "characters.json").is_file()
    assert (dest / "src" / "brotato" / "app.py").is_file()
    assert not (dest / ".git").exists()
    assert not (dest / ".venv").exists()

    # Verify extracted folder runs cleanly using current Python environment
    env = dict(os.environ)
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"
    smoke = subprocess.run(
        [sys.executable, str(dest / "main.py"), "--headless-smoke"],
        cwd=str(dest),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Headless smoke test passed!" in smoke.stdout


def test_download_script_zip_only_and_package_zip(tmp_path: Path) -> None:
    dest_prefix = tmp_path / "Brotato-Bundle"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "download_brotato.py"),
            "--local-repo",
            str(ROOT),
            "--dest",
            str(dest_prefix),
            "--zip-only",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    zip_path = tmp_path / "Brotato-Bundle.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        assert "Brotato-Bundle/main.py" in names
        assert "Brotato-Bundle/Play_Brotato.bat" in names
        assert "Brotato-Bundle/play_brotato.sh" in names
        assert "Brotato-Bundle/data/weapons.json" in names
        assert not any(".git/" in n or ".venv/" in n for n in names)

    pkg_zip = tmp_path / "pkg.zip"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "package_zip.py"), "--out", str(pkg_zip)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert pkg_zip.is_file()
    with zipfile.ZipFile(pkg_zip, "r") as zf:
        assert "pkg/main.py" in set(zf.namelist())
