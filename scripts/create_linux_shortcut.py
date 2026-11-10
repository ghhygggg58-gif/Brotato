#!/usr/bin/env python3
"""Creates Linux Mint / XDG desktop shortcut, app-menu entry, icon, and `brotato` CLI command."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def _generate_icon(game_dir: Path, icon_dest: Path) -> bool:
    """Render the potato character sprite to a 128x128 PNG icon."""
    icon_dest.parent.mkdir(parents=True, exist_ok=True)
    venv_py = game_dir / ".venv" / "bin" / "python"
    py_exe = str(venv_py) if venv_py.is_file() else sys.executable

    code = (
        "import os, sys; "
        "os.environ['SDL_VIDEODRIVER']='dummy'; "
        "os.environ['SDL_AUDIODRIVER']='dummy'; "
        f"sys.path.insert(0, {str(game_dir / 'src')!r}); "
        "import pygame; pygame.init(); "
        "pygame.display.set_mode((1, 1)); "
        "from brotato.data_loader import load_database; "
        "from brotato.sprites import SpriteAtlas; "
        "db = load_database(); "
        "atlas = SpriteAtlas(db); "
        "s = pygame.transform.smoothscale(atlas.get_character('well_rounded'), (128, 128)); "
        f"pygame.image.save(s, {str(icon_dest)!r}); "
        "pygame.quit()"
    )
    try:
        subprocess.run([py_exe, "-c", code], check=True, capture_output=True, timeout=20)
        return icon_dest.is_file()
    except Exception:
        return False


def create_shortcuts(
    game_dir: Path,
    home_dir: Path | None = None,
    create_desktop: bool = True,
) -> dict[str, Path]:
    home = (home_dir or Path.home()).resolve()
    game_dir = game_dir.resolve()
    launcher = game_dir / "play_brotato.sh"

    local_bin = home / ".local" / "bin"
    apps_dir = home / ".local" / "share" / "applications"
    icons_dir = home / ".local" / "share" / "icons" / "hicolor" / "128x128" / "apps"
    desktop_dir = home / "Desktop"

    local_bin.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)

    icon_path = icons_dir / "brotato-python.png"
    has_icon = _generate_icon(game_dir, icon_path)
    icon_field = str(icon_path) if has_icon else "applications-games"

    # 1. ~/.local/bin/brotato CLI command
    bin_cmd = local_bin / "brotato"
    bin_cmd.write_text(
        f"#!/usr/bin/env bash\nexec {str(launcher)!r} \"$@\"\n",
        encoding="utf-8",
    )
    os.chmod(bin_cmd, 0o755)

    # 2. .desktop content (works across Linux Mint Cinnamon, MATE, XFCE, Ubuntu, etc.)
    desktop_body = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        "Name=Brotato (Python)\n"
        "Comment=Play Brotato Python (Pygame-CE Edition)\n"
        f"Exec=\"{launcher}\"\n"
        f"Path={game_dir}\n"
        f"Icon={icon_field}\n"
        "Terminal=false\n"
        "Categories=Game;ActionGame;\n"
        "StartupNotify=true\n"
    )

    menu_entry = apps_dir / "brotato-python.desktop"
    menu_entry.write_text(desktop_body, encoding="utf-8")
    os.chmod(menu_entry, 0o755)

    created: dict[str, Path] = {
        "bin": bin_cmd,
        "menu_entry": menu_entry,
    }
    if has_icon:
        created["icon"] = icon_path

    # 3. Desktop shortcut (~/Desktop/Brotato.desktop)
    if create_desktop and desktop_dir.is_dir():
        desk_entry = desktop_dir / "Brotato.desktop"
        desk_entry.write_text(desktop_body, encoding="utf-8")
        os.chmod(desk_entry, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        gio_exe = shutil.which("gio")
        if gio_exe:
            subprocess.run(
                [gio_exe, "set", str(desk_entry), "metadata::trusted", "true"],
                capture_output=True,
                check=False,
            )
        created["desktop_entry"] = desk_entry

    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Linux Mint / XDG shortcuts for Brotato Python.")
    parser.add_argument("--game-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--no-desktop", action="store_true")
    args = parser.parse_args()

    res = create_shortcuts(args.game_dir, create_desktop=not args.no_desktop)
    for key, path in res.items():
        print(f"Created {key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
