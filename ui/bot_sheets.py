"""Bot-specific sheets: bot info, appearance editor and the bot library manager."""
from __future__ import annotations

import configparser
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QCompleter, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from ui import loadout
from ui.dialogs import Sheet, Spinner, rule, text_label

_logo_cache = {}
ASSETS = Path(__file__).resolve().parent / "assets"


def _tile(size, color="#2a2e33"):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    radius = max(3, size // 7)
    painter.drawRoundedRect(0, 0, size, size, radius, radius)
    return pix, painter


def kind_icon(kind, size=24):
    """Icon tile for players that aren't bots: "human" or "psyonix"."""
    key = (kind, size)
    if key not in _logo_cache:
        pix, painter = _tile(size)
        inset = round(size * 0.16)
        QSvgRenderer(str(ASSETS / f"{kind}.svg")).render(
            painter, QRectF(inset, inset, size - 2 * inset, size - 2 * inset))
        painter.end()
        _logo_cache[key] = pix
    return _logo_cache[key]


def letter_tile(name, size=24):
    """First letter of the bot's name on a muted tile, tinted per name."""
    letter = next((c for c in str(name or "") if c.isalnum()), "?").upper()
    hue = sum(ord(c) for c in str(name or "")) * 37 % 360
    pix, painter = _tile(size, QColor.fromHsl(hue, 45, 62).name())
    font = QFont("Segoe UI")
    font.setPixelSize(round(size * 0.5))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#e8eaec"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    painter.end()
    return pix


def bot_logo(path, size=24, name=None):
    """Bot logo from logo_file in bot.cfg / bot.toml, or a logo.png beside it.

    Bots without one get a tile with the first letter of their name.
    """
    key = (str(path or ""), size, name)
    if key in _logo_cache:
        return _logo_cache[key]
    pix = QPixmap()
    if path:
        bot_file = Path(path)
        folder = bot_file.parent if bot_file.is_file() else bot_file
        candidates = []
        try:
            text = bot_file.read_text("utf-8", "replace") if bot_file.is_file() else ""
            match = re.search(r'^\s*logo_file\s*=\s*"?([^"\n]*?)"?\s*$', text, re.M)
            if match and match.group(1).strip():
                candidates.append(folder / match.group(1).strip())
        except OSError:
            pass
        candidates.append(folder / "logo.png")
        for candidate in candidates:
            if candidate.is_file() and pix.load(str(candidate)):
                break
    if pix.isNull():
        pix = letter_tile(name or (Path(path).parent.name if path else "?"), size)
    else:
        pix = pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    _logo_cache[key] = pix
    return pix


def open_folder(path):
    folder = Path(path)
    folder = folder if folder.is_dir() else folder.parent
    if sys.platform == "win32" and Path(path).is_file():
        subprocess.Popen(["explorer", "/select,", str(Path(path))])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def bot_details(path) -> dict:
    """Description, developer, etc. from the bot's [Details] / [details] section."""
    bot_file = Path(path)
    try:
        if bot_file.suffix.lower() == ".cfg":
            parser = configparser.RawConfigParser()
            parser.read(bot_file, encoding="utf-8")
            details = dict(parser.items("Details")) if parser.has_section("Details") else {}
        elif bot_file.suffix.lower() == ".toml":
            details = tomllib.loads(bot_file.read_text(encoding="utf-8")).get("details", {})
        else:
            details = {}
    except (OSError, configparser.Error, tomllib.TOMLDecodeError):
        details = {}
    clean = {k: str(v).strip() for k, v in details.items() if str(v).strip()}
    if "source_link" in clean and "github" not in clean:
        clean["github"] = clean["source_link"]
    return clean


def framework_tags(bot) -> list[str]:
    framework = (bot.get("diagnostics") or {}).get("framework") or ""
    tags = []
    if "v4" in framework or str(bot.get("path", "")).lower().endswith(".cfg"):
        tags.append("RLBot v4")
    elif "v5" in framework or str(bot.get("path", "")).lower().endswith(".toml"):
        tags.append("RLBot v5")
    if bot.get("category") == "ML":
        tags.append("Machine learning")
    return tags


def short_path(path, keep=2):
    parts = Path(path).parts
    return str(Path(*parts[-keep:])) if len(parts) > keep else str(path)


class _PackageCheck(QThread):
    done = Signal(bool)

    def __init__(self, path, parent):
        super().__init__(parent)  # parented to the window so it outlives the sheet
        self.path = path

    def run(self):
        try:
            from ui.bot_importer import discover
            from ui.preflight import dependencies_ready
            path = Path(self.path).resolve()
            chosen = next((c for c in discover(path) if c.path == path), None)
            self.done.emit(chosen is None or dependencies_ready(path, chosen))
        except Exception:
            self.done.emit(True)


class BotInfoSheet(Sheet):
    """Everything about one bot, with the actions you'd want next."""

    def __init__(self, owner, bot):
        details = bot_details(bot["path"])
        super().__init__(owner, bot["name"], details.get("developer", ""),
                         logo=bot_logo(bot["path"], 56, bot["name"]), width=480)
        self.owner, self.bot = owner, bot
        for tag in framework_tags(bot) + [t.strip() for t in details.get("tags", "").split(",") if t.strip()][:3]:
            self.add_tag(tag)
        self.tags.addStretch()
        if details.get("description"):
            self.body.addWidget(text_label(details["description"]))
        if details.get("fun_fact"):
            fact = text_label(details["fun_fact"], "SheetSub")
            self.body.addWidget(fact)
        self.body.addSpacing(4)
        self.body.addWidget(rule())
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        rows = [("Status", self._status())]
        if details.get("language"):
            rows.append(("Language", text_label(details["language"], "Value")))
        location = text_label(short_path(bot["path"]), "Value", False)
        location.setToolTip(bot["path"])
        rows.append(("Location", location))
        if details.get("github"):
            link = text_label(f'<a style="color:#8fb4d9" href="{details["github"]}">{details["github"]}</a>', "Value", False)
            link.setOpenExternalLinks(True)
            link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            rows.append(("Source", link))
        for row, (key, widget) in enumerate(rows):
            grid.addWidget(text_label(key, "Key", False), row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)
        warnings = (bot.get("diagnostics") or {}).get("warnings") or []
        for warning in warnings[:4]:
            self.body.addWidget(text_label("⚠  " + warning, "Warn"))

        self.add_button("Appearance", left=True, callback=self.edit_appearance)
        self.add_button("Open folder", left=True, callback=lambda: open_folder(bot["path"]))
        self.add_button("Add to Blue", "BlueBtn", callback=lambda: self.add(0))
        self.add_button("Add to Orange", "OrangeBtn", callback=lambda: self.add(1))

    def _status(self):
        """Status row. The package check takes seconds, so it runs in a thread."""
        box = QWidget()
        self.status_row = QHBoxLayout(box)
        self.status_row.setContentsMargins(0, 0, 0, 0)
        self.status_row.setSpacing(6)
        if not Path(self.bot["path"]).exists():
            self.status_row.addWidget(text_label("Bot files are missing", "Bad"))
            return box
        spinner = Spinner(12, "#8b9196")
        spinner.start()
        self.status_row.addWidget(spinner)
        self.status_row.addWidget(text_label("Checking packages…", "Key", False))
        self.status_row.addStretch()
        check = _PackageCheck(self.bot["path"], self.owner)
        check.done.connect(self._show_status)
        check.finished.connect(check.deleteLater)
        check.start()
        return box

    def _show_status(self, ready):
        try:
            row = self.status_row
            while row.count():
                item = row.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        except RuntimeError:
            return  # sheet already closed
        if ready:
            row.addWidget(text_label("Ready to play", "Ok", False))
        else:
            row.addWidget(text_label("Needs Python packages", "Warn", False))
            install = QPushButton("Install")
            install.setObjectName("Link")
            install.setCursor(Qt.CursorShape.PointingHandCursor)
            install.clicked.connect(lambda: (self.accept(), self.owner.install_bot_dependencies([self.bot])))
            row.addWidget(install)
        row.addStretch()

    def add(self, team):
        self.accept()
        self.owner.add_player("bot", team, self.bot["id"])

    def edit_appearance(self):
        self.accept()
        self.owner.edit_appearance(self.bot)


class ColorPopup(QFrame):
    """Grid of Rocket League paint swatches shown under a colour button."""

    def __init__(self, parent, colors, columns, selected, choose):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Sheet")
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(3)
        for index, rgb in enumerate(colors):
            swatch = QPushButton()
            swatch.setFixedSize(20, 20)
            border = "2px solid #ffffff" if index == selected else "1px solid rgba(0,0,0,90)"
            swatch.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]}); border:{border}; border-radius:3px; padding:0; min-height:0")
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.clicked.connect(lambda _, i=index: (choose(i), self.close()))
            grid.addWidget(swatch, index // columns, index % columns)


class ColorButton(QPushButton):
    def __init__(self, title, on_change):
        super().__init__()
        self.title, self.on_change = title, on_change
        self.colors, self.columns, self.value = [], 10, 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.pick)

    def set_palette(self, colors, columns, value):
        self.colors, self.columns = colors, columns
        self.set_value(value)

    def set_value(self, value):
        self.value = value if 0 <= value < len(self.colors) else 0
        rgb = self.colors[self.value] if self.colors else (90, 90, 90)
        swatch = QPixmap(14, 14)
        swatch.fill(QColor(*rgb))
        self.setIcon(QIcon(swatch))
        self.setText(f"  {self.title}")

    def pick(self):
        popup = ColorPopup(self, self.colors, self.columns, self.value,
                           lambda i: (self.set_value(i), self.on_change(i)))
        popup.move(self.mapToGlobal(QPoint(0, self.height() + 4)))
        popup.show()


def paint_icon(hex_color):
    pix = QPixmap(12, 12)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if hex_color:
        painter.setBrush(QColor(hex_color))
        painter.setPen(QColor(0, 0, 0, 80))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor("#6b7075"))
    painter.drawEllipse(1, 1, 10, 10)
    painter.end()
    return QIcon(pix)


class ItemCombo(QComboBox):
    """Searchable item picker: type any part of a name."""

    def __init__(self):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(16)
        self.setMinimumWidth(240)
        completer = self.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def fill(self, entries, value):
        self.blockSignals(True)
        self.clear()
        self.addItem("None", 0)
        for item_id, name in entries:
            self.addItem(name, item_id)
        index = self.findData(value)
        if index < 0 and value:
            self.addItem(f"Item {value}", value)
            index = self.count() - 1
        self.setCurrentIndex(max(0, index))
        self.blockSignals(False)

    def value(self):
        index = self.findText(self.currentText(), Qt.MatchFlag.MatchFixedString)
        return self.itemData(index if index >= 0 else self.currentIndex()) or 0


class AppearanceSheet(Sheet):
    """Edit the bot's car, items and colours for both teams."""

    def __init__(self, owner, bot):
        super().__init__(owner, "Appearance", bot["name"], logo=bot_logo(bot["path"], 40, bot["name"]), width=640)
        self.bot = bot
        self.data = loadout.load(Path(bot["path"]))
        self.team = "blue"
        catalogue = loadout.items()

        top = QHBoxLayout()
        top.setSpacing(0)
        self.team_buttons = {}
        for team, title in (("blue", "Blue"), ("orange", "Orange")):
            button = QPushButton(title)
            button.setObjectName("Seg")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _, t=team: self.switch(t))
            top.addWidget(button)
            self.team_buttons[team] = button
        top.addSpacing(14)
        self.primary = ColorButton("Primary colour", lambda v: self._set(self.team, "team_color_id", v))
        self.accent = ColorButton("Accent colour", lambda v: self._set(self.team, "custom_color_id", v))
        top.addWidget(self.primary)
        top.addSpacing(6)
        top.addWidget(self.accent)
        top.addStretch()
        self.body.addLayout(top)
        self.body.addWidget(rule())

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        self.combos, self.paints = {}, {}
        for row, (field, category, paint, title) in enumerate(loadout.ITEM_FIELDS):
            grid.addWidget(text_label(title, "Key", False), row, 0)
            combo = ItemCombo()
            if field == "decal_id":
                combo.currentIndexChanged.connect(lambda *_: None)
            elif field == "car_id":
                combo.activated.connect(lambda *_: self._car_changed())
                combo.lineEdit().editingFinished.connect(self._car_changed)
            self.combos[field] = (combo, catalogue.get(category, []))
            grid.addWidget(combo, row, 1)
            if paint:
                paints = QComboBox()
                for paint_id, name, color in loadout.PAINTS:
                    paints.addItem(paint_icon(color), name, paint_id)
                paints.setMinimumWidth(150)
                self.paints[paint] = paints
                grid.addWidget(paints, row, 2)
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)
        self.same = QCheckBox("Use the same items for both teams")
        self.body.addWidget(self.same)

        self.add_button("Randomize", left=True, callback=self.randomize)
        self.add_button("Reset", left=True, callback=self.reset)
        self.add_button("Cancel", result=False)
        self.add_button("Save", "Primary", result=True)
        self.switch("blue")

    def _set(self, team, field, value):
        self.data[team][field] = value

    def _car_changed(self):
        combo, _ = self.combos["decal_id"]
        current = combo.value()
        combo.fill(loadout.decals_for(self.combos["car_id"][0].value()), current)

    def store(self):
        """Copy what's on screen into self.data for the current team."""
        team = self.team
        for field, (combo, _) in self.combos.items():
            self.data[team][field] = int(combo.value())
        for field, combo in self.paints.items():
            self.data[f"{team}_paint"][field] = int(combo.currentData())

    def show_team(self):
        team = self.team
        values, paints = self.data[team], self.data[f"{team}_paint"]
        palette = loadout.palettes()
        self.primary.set_palette(palette[team], 10, values["team_color_id"])
        self.accent.set_palette(palette["secondary"], 15, values["custom_color_id"])
        for field, (combo, entries) in self.combos.items():
            if field == "decal_id":
                entries = loadout.decals_for(values["car_id"])
            combo.fill(entries, values[field])
        for field, combo in self.paints.items():
            combo.setCurrentIndex(max(0, combo.findData(paints[field])))

    def switch(self, team):
        if self.isVisible() or team != self.team:
            self.store()
        self.team = team
        for name, button in self.team_buttons.items():
            button.setChecked(name == team)
        self.show_team()

    def randomize(self):
        self.store()
        loadout.randomize(self.team, self.data)
        self.show_team()

    def reset(self):
        for key in (self.team, f"{self.team}_paint"):
            self.data[key] = dict(loadout.DEFAULT[key])
        self.show_team()

    def accept(self):
        self.store()
        if self.same.isChecked():
            other = "orange" if self.team == "blue" else "blue"
            colors = {k: self.data[other][k] for k in loadout.COLOR_FIELDS}
            self.data[other] = {**self.data[self.team], **colors}
            self.data[f"{other}_paint"] = dict(self.data[f"{self.team}_paint"])
        super().accept()

    def save(self):
        return loadout.save(Path(self.bot["path"]), self.data)


class ManageBotsSheet(Sheet):
    """The bot library: every imported bot with its location and actions."""

    def __init__(self, owner):
        super().__init__(owner, "Bot library", "Imported bots. Removing one keeps its files on disk.", width=640)
        self.owner = owner
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(min(420, max(120, 52 * len(owner.bots))))
        content = QWidget()
        content.setObjectName("BotContent")
        self.rows = QVBoxLayout(content)
        self.rows.setContentsMargins(0, 0, 6, 0)
        self.rows.setSpacing(4)
        scroll.setWidget(content)
        self.body.addWidget(scroll)
        self.render()
        self.add_button("Import bot…", left=True, callback=lambda: (self.accept(), owner.import_file()))
        self.add_button("Import folder…", left=True, callback=lambda: (self.accept(), owner.import_folder()))
        self.add_button("Done", "Primary", result=True)

    def render(self):
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.owner.bots:
            self.rows.addWidget(text_label("No bots yet. Import a bot folder, archive, bot.cfg or bot.toml.", "SheetSub"))
        for bot in self.owner.bots:
            row = QFrame()
            row.setObjectName("Row")
            line = QHBoxLayout(row)
            line.setContentsMargins(6, 6, 8, 6)
            line.setSpacing(10)
            logo = QLabel()
            logo.setPixmap(bot_logo(bot["path"], 32, bot["name"]))
            line.addWidget(logo)
            names = QVBoxLayout()
            names.setSpacing(1)
            names.addWidget(text_label(bot["name"], "Value", False))
            where = text_label(short_path(bot["path"], 3), "Key", False)
            where.setToolTip(bot["path"])
            names.addWidget(where)
            line.addLayout(names, 1)
            for title, callback in (("Info", lambda _, b=bot: self.owner.show_bot_details(b)),
                                    ("Open folder", lambda _, b=bot: open_folder(b["path"])),
                                    ("Remove", lambda _, b=bot: self.remove(b))):
                button = QPushButton(title)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(callback)
                line.addWidget(button)
            self.rows.addWidget(row)
        self.rows.addStretch()

    def remove(self, bot):
        if self.owner.remove_bot(bot):
            self.render()
