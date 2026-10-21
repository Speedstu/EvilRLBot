"""Validate desktop icon metadata and extracted AppImage icons before release."""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 24:
        raise AssertionError(f"Invalid PNG: {path}")
    return struct.unpack(">II", data[16:24])


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(appdir: Path) -> None:
    sources = {
        "512": REPO / "ui/assets/logo.png",
        "128": REPO / "packaging/icons/evil-rlbot-128.png",
    }
    assert png_size(sources["512"]) == (512, 512)
    assert png_size(sources["128"]) == (128, 128)
    targets = {
        "512": appdir / "usr/share/icons/hicolor/512x512/apps/evil-rlbot.png",
        "128": appdir / "usr/share/icons/hicolor/128x128/apps/evil-rlbot.png",
    }
    for label in ("512", "128"):
        assert sha(sources[label]) == sha(targets[label]), f"{label}px icon is stale"

    root_icon = appdir / "evil-rlbot.png"
    dir_icon = appdir / ".DirIcon"
    assert root_icon.is_symlink(), "AppImage root icon must link to theme icon"
    assert dir_icon.is_symlink(), "Missing AppImage .DirIcon"
    assert sha(root_icon) == sha(sources["512"]), "AppImage root still uses an old icon"
    assert sha(dir_icon) == sha(sources["512"]), "AppImage thumbnail still uses an old icon"
    desktop_source = (REPO / "packaging/evil-rlbot.desktop").read_text(encoding="utf-8")
    # appimagetool adds AppImage-specific metadata to the root desktop file.
    # Compare the icon / window matching settings rather than byte-for-byte.
    from configparser import ConfigParser
    def parsed_desktop(text: str):
        parser = ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        parser.read_string(text)
        return parser["Desktop Entry"]
    expected = parsed_desktop(desktop_source)
    for desktop_path in (
        appdir / "evil-rlbot.desktop",
        appdir / "usr/share/applications/evil-rlbot.desktop",
    ):
        actual = parsed_desktop(desktop_path.read_text(encoding="utf-8"))
        for field in ("Name", "Icon", "StartupWMClass", "Type"):
            assert actual.get(field) == expected.get(field), (
                f"Desktop {field} is stale in {desktop_path}: "
                f"{actual.get(field)!r} != {expected.get(field)!r}")
    assert expected.get("Icon") == "evil-rlbot"
    assert expected.get("StartupWMClass") == "evil-rlbot"
    assert "app.setDesktopFileName(\"evil-rlbot\")" in (
        REPO / "ui/classic.py").read_text(encoding="utf-8")
    assert "app.setWindowIcon(logo_icon())" in (
        REPO / "ui/classic.py").read_text(encoding="utf-8")
    print("LINUX_DOCK_ICON_VALID: 128px/512px theme, .DirIcon, Qt and desktop entry")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <extracted-AppDir>")
    check(Path(sys.argv[1]))
