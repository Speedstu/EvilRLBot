#!/usr/bin/env python3
"""Classic RLBot-style native Qt match setup, backed by RLBotServer v5.

Layout follows the user's actual RLBot v4 GUI reference: black toolbar,
light Bot Library with compact bot chips, bold Blue/Orange team panels and a
small bottom Match Settings bar. No browser, Electron, or web server.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMenu, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui import bot_importer, server, offline_launcher
from ui.match_config import validate_setup
from ui.native import MAPS, MODES, LAUNCHERS, logo_icon
from ui.dialogs import (DIALOG_CSS, ExtraSheet, LogsSheet, MutatorsSheet, ProgressSheet, Sheet, Spinner,
                        Toast, confirm, message, text_label)
from ui.bot_sheets import AppearanceSheet, BotInfoSheet, ManageBotsSheet, bot_logo, kind_icon, open_folder

CSS = """
QMainWindow, QWidget#Main {background:#15181b; color:#e4e6e8; font:13px 'Segoe UI','Noto Sans',Arial,sans-serif}
QWidget {color:#e4e6e8; font:13px 'Segoe UI','Noto Sans',Arial,sans-serif}
QToolTip {background:#1d2024; color:#e4e6e8; border:1px solid #3a3f44; padding:5px}
QFrame#Header {background:rgba(0,0,0,170)}
QLabel {background:transparent}
QLabel#HeaderName {color:#ffffff; font:700 20px 'Segoe UI','Noto Sans',Arial}
QFrame#Panel {background:rgba(12,14,16,220); border-radius:6px}
QFrame#Blue, QFrame#Orange {background:rgba(12,14,16,220); border-radius:6px}
QFrame#BlueHead, QFrame#OrangeHead {border-top-left-radius:6px; border-top-right-radius:6px}
QFrame#BlueHead {background:#0d5bb0}
QFrame#OrangeHead {background:#ea6b1e}
QLabel#TeamHead {color:#fff; font-weight:700}
QLabel#Headline {font:700 20px 'Segoe UI','Noto Sans',Arial; color:#fff}
QLabel#Hint {color:#7d8388; font-size:11px}
QLabel#Empty {color:#7d8388; font-style:italic; padding:6px 2px}
QPushButton {border:none; background:#24282c; border-radius:4px; color:#e4e6e8; padding:6px 11px; min-height:18px}
QPushButton:hover {background:#2f3439}
QPushButton:pressed {background:#383e44}
QPushButton:disabled {color:#6b7075}
QPushButton#Start {background:#237a2f; color:#fff; font-weight:600; padding:7px 18px}
QPushButton#Start:hover {background:#2a8e38}
QPushButton#Start:disabled {background:#1f4425; color:#8fa894}
QPushButton#Stop {background:#b42323; color:#fff; font-weight:600; padding:7px 14px}
QPushButton#Stop:hover {background:#c92b2b}
QPushButton#Filter {border:1px solid #3a3f44; border-radius:0; background:transparent; padding:5px 12px; font-size:12px}
QPushButton#Filter:hover {background:#24282c}
QPushButton#Filter:checked {background:#f1f3f4; color:#1b1d1f; border-color:#f1f3f4}
QFrame#BotTile, QFrame#Slot {background:#1d2024; border-radius:4px}
QFrame#BotTile:hover {background:#2a2e33}
QPushButton#Info {background:#3b4045; color:#c5c9cc; border-radius:7px; padding:0; min-height:14px; max-height:14px; min-width:14px; max-width:14px; font:italic 700 10px 'Segoe UI',Arial}
QPushButton#Info:hover {background:#4b5157}
QPushButton#SlotRemove {color:#ff7070; background:transparent; font-size:15px; padding:0 4px; min-width:16px}
QPushButton#SlotRemove:hover {color:#ff9a9a}
QPushButton#AddTeam {background:transparent; color:#7d8388; text-align:left; padding:6px 12px; font-size:12px}
QPushButton#AddTeam:hover {color:#fff}
QLineEdit {background:transparent; border:1px solid #3a3f44; border-radius:4px; padding:5px 9px; color:#e4e6e8}
QLineEdit:focus {border-color:#7d8388}
QComboBox {background:#f1f3f4; color:#1b1d1f; border:none; border-radius:4px; padding:5px 10px; min-height:18px}
QComboBox::drop-down {border:none; width:20px}
QComboBox QAbstractItemView {background:#f1f3f4; color:#1b1d1f; selection-background-color:#d4d8db; selection-color:#1b1d1f; outline:0}
QScrollArea {border:0; background:transparent}
QWidget#BotContent {background:transparent}
QScrollBar:vertical {background:transparent; width:8px}
QScrollBar::handle:vertical {background:#3a3f44; border-radius:4px; min-height:24px}
QScrollBar::add-line, QScrollBar::sub-line {height:0}
QMenu {background:#1d2024; border:1px solid #3a3f44; color:#e4e6e8; padding:4px}
QMenu::item {padding:6px 16px}
QMenu::item:selected {background:#2f3439}
QMenu::separator {height:1px; background:#3a3f44; margin:4px 6px}
QDialog {background:#15181b}
QPlainTextEdit {background:#0e1012; color:#d6d8da; border:1px solid #2a2e33; border-radius:4px; font-family:Consolas,'DejaVu Sans Mono',monospace}
"""
CSS += "QComboBox::down-arrow {image:url(%s); width:10px; height:6px}" % (
    ROOT / "ui/assets/chevron-down.svg").as_posix()

CSS += DIALOG_CSS
# Inside dialogs, dropdowns are dark so long forms stay calm.
CSS += """
QFrame#Sheet QComboBox {background:#1f2327; color:#e4e6e8; border:1px solid #30353b}
QFrame#Sheet QComboBox:hover {border-color:#454b52}
QFrame#Sheet QComboBox:focus {border-color:#6b7178}
QFrame#Sheet QComboBox QAbstractItemView {background:#1f2327; color:#e4e6e8; selection-background-color:#2f3439; selection-color:#fff}
QFrame#Sheet QComboBox::down-arrow {image:url(%s)}
QFrame#Sheet QLineEdit {background:#1f2327; border:1px solid #30353b}
QCheckBox::indicator:checked {image:url(%s)}
""" % ((ROOT / "ui/assets/chevron-down-light.svg").as_posix(), (ROOT / "ui/assets/check.svg").as_posix())
LOGO_SIZE = 24


def chip_row(widget, logo_path, name, icon=None):
    """Logo + name row shared by library chips and team slots."""
    row = QHBoxLayout(widget)
    row.setContentsMargins(3, 3, 8, 3)
    row.setSpacing(7)
    logo = QLabel()
    logo.setPixmap(icon or bot_logo(logo_path, LOGO_SIZE, name))
    logo.setFixedSize(LOGO_SIZE, LOGO_SIZE)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    row.addWidget(logo)
    row.addWidget(QLabel(name), 1)
    return row


def info_button(callback):
    button = QPushButton("i")
    button.setObjectName("Info")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(callback)
    return button


HUMAN_ID = "__human__"


class DragTile(QFrame):
    def __init__(self, bot, owner):
        super().__init__()
        self.owner = owner
        self.bot = bot
        self.human = bot["id"] == HUMAN_ID
        self.setObjectName("BotTile")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if self.human:
            self.setToolTip("You — click or drag onto a team")
            chip_row(self, None, "Human", kind_icon("human", LOGO_SIZE))
        else:
            self.setToolTip(f'{bot["name"]}\n{bot["path"]}\n{bot["diagnostics"].get("framework","Unknown")} — click or drag to a team')
            row = chip_row(self, bot["path"], bot["name"])
            row.addWidget(info_button(lambda: owner.show_bot_details(bot)))
        self.start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            if self.human:
                return
            self.owner.show_bot_details(self.bot)
            return
        self.start_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.start_pos is not None and (event.pos() - self.start_pos).manhattanLength() > 10 and event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-evilrlbot-bot", self.bot["id"].encode())
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            self.start_pos = None
            drag.exec(Qt.DropAction.CopyAction)

    def mouseReleaseEvent(self, event):
        if self.start_pos is not None and event.button() == Qt.MouseButton.LeftButton:
            if self.human:
                self.owner.add_player("human", self.owner.next_team())
            else:
                self.owner.add_player("bot", self.owner.next_team(), self.bot["id"])
        self.start_pos = None


class Team(QFrame):
    def __init__(self, owner, team):
        super().__init__()
        self.owner, self.team = owner, team
        self.setObjectName("Blue" if team == 0 else "Orange")
        self.setAcceptDrops(True)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 4)
        col.setSpacing(0)
        bar = QFrame()
        bar.setObjectName("BlueHead" if team == 0 else "OrangeHead")
        head = QHBoxLayout(bar)
        head.setContentsMargins(12, 5, 12, 5)
        self.head_count = QLabel()
        for label in (QLabel("BLUE TEAM" if team == 0 else "ORANGE TEAM"), self.head_count):
            label.setObjectName("TeamHead")
            head.addWidget(label)
        head.insertStretch(1)
        col.addWidget(bar)
        self.slots = QVBoxLayout()
        self.slots.setContentsMargins(10, 10, 10, 0)
        self.slots.setSpacing(5)
        col.addLayout(self.slots)
        col.addStretch()
        add = QPushButton("+  Add to Blue Team" if team == 0 else "+  Add to Orange Team")
        add.setObjectName("AddTeam")
        add.clicked.connect(lambda: owner.add_menu(add, team))
        col.addWidget(add, 0)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-evilrlbot-bot") or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-evilrlbot-bot") or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-evilrlbot-bot"):
            bot_id = bytes(event.mimeData().data("application/x-evilrlbot-bot")).decode()
            if bot_id == HUMAN_ID:
                self.owner.add_player("human", self.team)
            else:
                self.owner.add_player("bot", self.team, bot_id)
        elif event.mimeData().hasUrls():
            self.owner.import_urls(event.mimeData().urls(), target_team=self.team)
        event.acceptProposedAction()

    def redraw(self):
        while self.slots.count():
            item = self.slots.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        players = [(i, p) for i, p in enumerate(self.owner.setup["players"]) if p["team"] == self.team]
        bots = sum(p["kind"] != "human" for _, p in players)
        self.head_count.setText(f"{bots} BOT{'' if bots == 1 else 'S'}")
        if not players:
            l = QLabel("Drop bots here...")
            l.setObjectName("Empty")
            self.slots.addWidget(l)
        for index, player in players:
            found = None
            if player["kind"] == "human":
                name = "Human"
            elif player["kind"] == "psyonix":
                name = "Psyonix " + player.get("skill", "Pro")
            else:
                found = self.owner.get_bot(player.get("id"))
                name = found["name"] if found else "Missing bot"
            row = QFrame()
            row.setObjectName("Slot")
            row.setToolTip("Right click to move to the other team")
            row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            row.customContextMenuRequested.connect(lambda pos, idx=index, w=row: self.owner.slot_menu(w, pos, idx))
            icon = kind_icon(player["kind"], LOGO_SIZE) if player["kind"] in ("human", "psyonix") else None
            layout = chip_row(row, found["path"] if found else None, name, icon)
            if found:
                layout.addWidget(info_button(lambda _, b=found: self.owner.show_bot_details(b)))
            remove = QPushButton("×")
            remove.setObjectName("SlotRemove")
            remove.setToolTip("Remove player")
            remove.clicked.connect(lambda _, i=index: self.owner.remove_player(i))
            layout.addWidget(remove)
            self.slots.addWidget(row)


class Background(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        from PySide6.QtGui import QLinearGradient
        wallpaper = ROOT / "ui/assets/arena-blur.jpg"
        if wallpaper.exists():
            img = QPixmap(str(wallpaper))
            painter.drawPixmap(self.rect(), img, img.rect())
            painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        else:
            g = QLinearGradient(0, 0, self.width(), self.height())
            g.setColorAt(0, QColor("#2c4245"))
            g.setColorAt(1, QColor("#172c31"))
            painter.fillRect(self.rect(), g)
        painter.end()


class ImportTask(QThread):
    imported = Signal(object)
    failed = Signal(str)

    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        try:
            result = []
            for p in self.paths:
                result.extend(bot_importer.import_path(Path(p)))
            # Checking whether a bot's packages are already usable can take
            # seconds (it probes Python runtimes), so do it here, not in the UI.
            for item in result:
                item["needs_install"] = bool(item.get("requirements")) and not packages_ready(item["path"])
            self.imported.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


def packages_ready(path):
    """True when the bot's required packages already import in some runtime."""
    from ui.preflight import dependencies_ready
    path = Path(path)
    chosen = next((c for c in bot_importer.discover(path) if c.path == path), None)
    return chosen is None or dependencies_ready(chosen.path, chosen)


class InstallTask(QThread):
    ready = Signal(str)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, path, requirements, framework, backend="cpu"):
        super().__init__()
        self.path, self.requirements, self.framework, self.backend = (
            path, requirements, framework, backend
        )

    def run(self):
        try:
            # Never download again when everything is already installed, e.g.
            # a bot that was queued twice or fixed by a previous install.
            if packages_ready(self.path):
                self.ready.emit("Packages already installed")
                return
            message = bot_importer.install_dependencies(
                Path(self.path), Path(self.requirements), self.framework,
                torch_backend=self.backend,
                progress=self.progress.emit,
                stop_requested=self.isInterruptionRequested,
            )
            self.ready.emit(message)
        except Exception as exc:
            self.failed.emit(str(exc))


class ClassicWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evil RLBot")
        self.setWindowIcon(logo_icon())
        self.resize(1250, 780)
        self.setMinimumSize(900, 610)
        self.setAcceptDrops(True)
        self.bots = []
        self.setup = server._load_setup()
        self.setup.setdefault("launcher", "OfflineLegendary")
        self._jobs = []
        self._busy = False
        self._install_queue = []
        self._install_backend = "cpu"
        self._install_dialog = None
        self._install_after_failed_match = False
        self._selected_filter = "All"
        self._last_columns = 0
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1500)
        self._ui()
        self.refresh_bots()
        self.redraw()
        self.update_status()
        QApplication.instance().installEventFilter(self)

    def _ui(self):
        background = Background()
        background.setObjectName("Main")
        self.setCentralWidget(background)
        page = QVBoxLayout(background)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(48)
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 6, 16, 6)
        h.setSpacing(6)
        mark = QLabel()
        mark.setPixmap(logo_icon().pixmap(30, 30))
        h.addWidget(mark)
        h.addSpacing(2)
        brand = QLabel("Evil RLBot")
        brand.setObjectName("HeaderName")
        h.addWidget(brand)
        h.addStretch()
        logs = QPushButton("Logs")
        logs.clicked.connect(self.show_logs)
        h.addWidget(logs)
        menu_button = QPushButton("Menu")
        menu_button.clicked.connect(lambda: self.top_menu(menu_button))
        h.addWidget(menu_button)
        page.addWidget(header)

        area = QVBoxLayout()
        area.setContentsMargins(12, 12, 12, 12)
        area.setSpacing(12)
        page.addLayout(area, 1)

        library = QFrame()
        library.setObjectName("Panel")
        self.library_panel = library
        lib = QVBoxLayout(library)
        lib.setContentsMargins(14, 12, 14, 12)
        lib.setSpacing(10)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.title("Bots"))
        controls.addSpacing(4)
        add = QPushButton("Add/Remove")
        add.clicked.connect(lambda: self.import_menu(add))
        controls.addWidget(add)
        manage = QPushButton("Manage bot folders")
        manage.clicked.connect(self.manage_bots)
        controls.addWidget(manage)
        controls.addStretch()
        self.spinner = Spinner()
        controls.addWidget(self.spinner)
        self.import_text = QLabel()
        self.import_text.setToolTip("ZIP, RAR, 7Z, folder, bot.cfg or bot.toml")
        self.import_text.setObjectName("Hint")
        controls.addWidget(self.import_text)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search...")
        self.search.setFixedWidth(180)
        self.search.textChanged.connect(self.render_library)
        controls.addWidget(self.search)
        lib.addLayout(controls)
        filters = QHBoxLayout()
        filters.setSpacing(0)
        filters.addStretch()
        for text in ["All", "Standard", "Extra modes", "Special bots/scripts", "Bots for 1v1", "Bots with teamplay", "Goalie bots"]:
            b = QPushButton(text)
            b.setObjectName("Filter")
            b.setCheckable(True)
            b.setChecked(text == "All")
            b.clicked.connect(lambda checked, name=text: self.set_filter(name))
            filters.addWidget(b)
            setattr(self, "_filter_" + text.replace(" ", "_"), b)
        filters.addStretch()
        lib.addLayout(filters)
        self.bot_scroll = QScrollArea()
        self.bot_scroll.setWidgetResizable(True)
        self.bot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bot_content = QWidget()
        self.bot_content.setObjectName("BotContent")
        self.bot_grid = QGridLayout(self.bot_content)
        self.bot_grid.setContentsMargins(0, 0, 0, 0)
        self.bot_grid.setHorizontalSpacing(5)
        self.bot_grid.setVerticalSpacing(5)
        self.bot_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bot_scroll.setWidget(self.bot_content)
        lib.addWidget(self.bot_scroll)
        area.addWidget(library, 0)

        teams = QHBoxLayout()
        teams.setSpacing(12)
        self.blue = Team(self, 0)
        self.orange = Team(self, 1)
        teams.addWidget(self.blue, 1)
        teams.addWidget(self.orange, 1)
        area.addLayout(teams, 1)

        settings = QFrame()
        settings.setObjectName("Panel")
        bottom = QVBoxLayout(settings)
        bottom.setContentsMargins(14, 12, 14, 12)
        bottom.setSpacing(10)
        bottom.addWidget(self.title("Match Settings"))
        bar = QHBoxLayout()
        bar.setSpacing(8)
        for choices, key, width in [(MAPS, "map", 190), (MODES, "mode", 130)]:
            combo = QComboBox()
            for name, val in choices:
                combo.addItem(name, val)
            combo.setMinimumWidth(width)
            combo.currentIndexChanged.connect(self.apply_settings)
            setattr(self, key + "_combo", combo)
            bar.addWidget(combo)
        for caption, callback in [("Mutators", self.show_mutators), ("Extra", self.show_extra)]:
            bar.addWidget(QPushButton(caption, clicked=callback))
        bar.addStretch()
        self.launcher_combo = QComboBox()
        for name, value in LAUNCHERS:
            self.launcher_combo.addItem(name, value)
        self.launcher_combo.currentIndexChanged.connect(self.apply_settings)
        self.launcher_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.launcher_combo.setMinimumContentsLength(18)
        self.launcher_combo.setToolTip("Launcher")
        bar.addWidget(self.launcher_combo)
        self.start = QPushButton("Start Match")
        self.start.setObjectName("Start")
        self.start.clicked.connect(self.start_match)
        bar.addWidget(self.start)
        stop = QPushButton("Stop")
        stop.setObjectName("Stop")
        stop.clicked.connect(self.stop_match)
        bar.addWidget(stop)
        bottom.addLayout(bar)
        self.status = QLabel("Ready")
        self.status.setObjectName("Hint")
        bottom.addWidget(self.status)
        area.addWidget(settings, 0)

    @staticmethod
    def title(text):
        lbl = QLabel(text)
        lbl.setObjectName("Headline")
        return lbl

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "bot_grid"):
            self.render_library()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.DragEnter and event.mimeData().hasUrls():
            if any(url.isLocalFile() for url in event.mimeData().urls()):
                event.acceptProposedAction()
                return True
        if event.type() == QEvent.Type.Drop and event.mimeData().hasUrls():
            if not isinstance(obj, Team):
                self.import_urls(event.mimeData().urls())
                event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)

    def get_bot(self, id):
        return next((b for b in self.bots if b["id"] == id), None)

    def refresh_bots(self):
        self.bots = [server._bot_payload(b) for b in server._load_library()]
        self.render_library()

    def set_filter(self, name):
        self._selected_filter = name
        for key in ["All", "Standard", "Extra modes", "Special bots/scripts", "Bots for 1v1", "Bots with teamplay", "Goalie bots"]:
            b = getattr(self, "_filter_" + key.replace(" ", "_"))
            b.setChecked(name == key)
        self.render_library()

    def render_library(self, *_):
        if not hasattr(self, "bot_grid") or not hasattr(self, "search"):
            return
        while self.bot_grid.count():
            item = self.bot_grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        q = self.search.text().strip().lower()
        bots = []
        for b in self.bots:
            if q and q not in f"{b['name']} {b['path']} {b['diagnostics']}".lower():
                continue
            if self._selected_filter == "Standard" and b.get("category") == "ML":
                continue
            if self._selected_filter == "Extra modes" and not any(x in b["name"].lower() for x in ["hoops", "dropshot", "snowday", "rumble"]):
                continue
            if self._selected_filter == "Special bots/scripts" and b.get("category") != "ML":
                continue
            if self._selected_filter == "Bots for 1v1" and not (b.get("favorite") or "1v1" in b["name"].lower()):
                continue
            if self._selected_filter == "Bots with teamplay" and not any(x in b["name"].lower() for x in ["2v2", "3v3", "team"]):
                continue
            if self._selected_filter == "Goalie bots" and "goalie" not in b["name"].lower():
                continue
            bots.append(b)
        if (self._selected_filter == "All" and (not q or q in "human you player")
                and not any(p["kind"] == "human" for p in self.setup["players"])):
            bots.insert(0, {"id": HUMAN_ID, "name": "Human"})
        col_count = max(2, min(8, (max(650, self.library_panel.width()) - 30) // 200))
        for index, b in enumerate(bots):
            self.bot_grid.addWidget(DragTile(b, self), index // col_count, index % col_count)
        for index in range(8):
            self.bot_grid.setColumnStretch(index, 1 if index < col_count else 0)
        # The panel fits its bots (up to four rows, then scrolls) instead of
        # leaving an empty area above the teams.
        rows = max(1, min(4, -(-len(bots) // col_count)))
        self.bot_scroll.setFixedHeight(rows * 30 + (rows - 1) * 5)
        if not self.spinner.active:
            self.import_text.setText(f"{len(self.bots)} bot{'' if len(self.bots) == 1 else 's'} · drop files here to import")

    def next_team(self):
        blue = sum(x["team"] == 0 for x in self.setup["players"])
        orange = sum(x["team"] == 1 for x in self.setup["players"])
        return 0 if blue <= orange else 1

    def player_name(self, player):
        if player["kind"] == "human":
            return "Human"
        if player["kind"] == "psyonix":
            return "Psyonix " + player.get("skill", "Pro")
        found = self.get_bot(player.get("id"))
        return found["name"] if found else "Missing bot"

    def add_player(self, kind, team, value=None):
        if len(self.setup["players"]) >= 10:
            self.toast("A match can have at most 10 players.", "warning")
            return
        if kind == "human" and any(x["kind"] == "human" for x in self.setup["players"]):
            self.toast("Only one human player is supported.", "warning")
            return
        if kind == "bot" and not self.get_bot(value):
            self.toast("Import this bot first.", "warning")
            return
        player = {"kind": kind, "team": team}
        if kind == "bot":
            player["id"] = value
        if kind == "psyonix":
            player["skill"] = value or "Pro"
        self.setup["players"].append(player)
        self.redraw()
        self.schedule_save()
        self.toast(f'{self.player_name(player)} added to {"Blue" if team == 0 else "Orange"}',
                   "blue" if team == 0 else "orange", ("Undo", lambda p=player: self._undo_add(p)))

    def _undo_add(self, player):
        if player in self.setup["players"]:
            self.setup["players"].remove(player)
            self.redraw()
            self.schedule_save()

    def remove_player(self, index):
        if len(self.setup["players"]) <= 1:
            self.toast("A match needs at least one player.", "warning")
            return
        player = self.setup["players"].pop(index)
        self.redraw()
        self.schedule_save()

        def undo():
            self.setup["players"].insert(min(index, len(self.setup["players"])), player)
            self.redraw()
            self.schedule_save()
        self.toast(f"{self.player_name(player)} removed", "info", ("Undo", undo))

    def slot_menu(self, source, pos, index):
        menu = QMenu(self)
        player = self.setup["players"][index]
        other = "Orange" if player["team"] == 0 else "Blue"
        menu.addAction(f"Move to {other}").triggered.connect(lambda: self.move_player(index))
        found = self.get_bot(player.get("id")) if player["kind"] == "bot" else None
        if found:
            menu.addAction("Bot info").triggered.connect(lambda: self.show_bot_details(found))
            menu.addAction("Appearance").triggered.connect(lambda: self.edit_appearance(found))
        menu.addSeparator()
        menu.addAction("Remove").triggered.connect(lambda: self.remove_player(index))
        menu.exec(source.mapToGlobal(pos))

    def move_player(self, index):
        self.setup["players"][index]["team"] = 1 - self.setup["players"][index]["team"]
        self.redraw()
        self.schedule_save()

    def add_menu(self, button_widget, team):
        menu = QMenu(self)
        menu.addSection("Players")
        for title, kind, val in [("Human", "human", None), ("Psyonix Rookie", "psyonix", "Rookie"),
                                 ("Psyonix Pro", "psyonix", "Pro"), ("Psyonix Allstar", "psyonix", "Allstar")]:
            act = menu.addAction(QIcon(kind_icon(kind, 20)), title)
            act.triggered.connect(lambda _, k=kind, v=val: self.add_player(k, team, v))
        if self.bots:
            menu.addSection("Bots")
        for bot in self.bots:
            act = menu.addAction(QIcon(bot_logo(bot["path"], 20, bot["name"])), bot["name"])
            act.triggered.connect(lambda _, id=bot["id"]: self.add_player("bot", team, id))
        menu.exec(button_widget.mapToGlobal(button_widget.rect().bottomLeft()))

    def redraw(self):
        for key, default in [("map", "Stadium_P"), ("mode", "Soccar"), ("launcher", "OfflineLegendary")]:
            combo = getattr(self, key + "_combo")
            combo.blockSignals(True)
            i = combo.findData(self.setup.get(key, default))
            if i >= 0:
                combo.setCurrentIndex(i)
            combo.blockSignals(False)
        self.blue.redraw()
        self.orange.redraw()
        # The Human chip appears in the library only while no human is playing.
        self.render_library()

    def apply_settings(self, *_):
        self.setup["map"] = self.map_combo.currentData()
        self.setup["mode"] = self.mode_combo.currentData()
        self.setup["launcher"] = self.launcher_combo.currentData()
        self.schedule_save()

    def show_mutators(self):
        sheet = MutatorsSheet(self, self.setup)
        if sheet.exec() and sheet.choice:
            self.setup["mutators"] = sheet.values()
            self.schedule_save()
            self.toast("Mutators saved", "success")

    def show_extra(self):
        sheet = ExtraSheet(self, self.setup)
        if sheet.exec() and sheet.choice:
            self.setup["options"] = sheet.values()
            self.schedule_save()
            self.toast("Extra settings saved", "success")

    def schedule_save(self):
        self.save_timer.start(350)

    def save(self):
        try:
            server._save_json(server.SETUP_FILE, validate_setup(self.setup, server._bot_paths()))
        except Exception as exc:
            self.status.setText("Setup error: " + str(exc))

    def update_status(self):
        status = server._status()
        if not status["running"]:
            self.status.setText("● Match stopped" if status["exit_code"] is not None else "● Ready")
            self.status.setStyleSheet("color:#7d8388")
            return
        # RLBotServer starts before bots are ready. Report actual bot status,
        # never "Match running" when initialization failed and the field is empty.
        tail = ""
        try:
            with server.LOG.open("rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 65536))
                tail = f.read().decode("utf-8", "replace")
        except OSError:
            pass
        if "CRITICAL:" in tail or "Spawning deferred due to unready agents" in tail and "exited with code" in tail:
            self.status.setText("⚠ Bot initialization failed — open Logs")
            self.status.setStyleSheet("color:#ff7070;font-weight:600")
            return
        counts = re.findall(r"Agents ready:\s*(\d+)\s*/\s*(\d+)", tail)
        if counts:
            count, total = map(int, counts[-1])
            if count < total:
                self.status.setText(f"◌ Initializing bots: {count}/{total}")
                self.status.setStyleSheet("color:#e0b04a")
                return
            self.status.setText(f"● Match running — {count}/{total} bots ready")
        else:
            self.status.setText("◌ Starting game and loading bots…")
        self.status.setStyleSheet("color:#6fcf7f")

    def toast(self, text, kind="info", action=None):
        Toast.show_message(self.centralWidget(), text, kind, action)

    def notice(self, text, title="Evil RLBot", kind="info"):
        message(self, title, text, kind=kind)

    def show_bot_details(self, bot):
        BotInfoSheet(self, bot).exec()

    def edit_appearance(self, bot):
        if not str(bot["path"]).lower().endswith((".cfg", ".toml")):
            self.notice("This bot has no bot.cfg or bot.toml, so its appearance can't be edited here.",
                        "Appearance", "warning")
            return
        sheet = AppearanceSheet(self, bot)
        if not (sheet.exec() and sheet.choice):
            return
        try:
            sheet.save()
        except Exception as exc:
            message(self, "Couldn't save appearance", "The bot's loadout file could not be written.",
                    kind="error", details=str(exc))
            return
        self.toast(f"Appearance saved for {bot['name']}", "success")

    def import_menu(self, widget):
        menu = QMenu(self)
        menu.addSection("Import")
        for name, callback in [("Bot file…", self.import_file), ("Bot folder…", self.import_folder),
                               ("ZIP, RAR or 7Z archive…", self.import_archive)]:
            menu.addAction(name).triggered.connect(callback)
        menu.addSection("Library")
        menu.addAction("Manage bots…").triggered.connect(self.manage_bots)
        menu.addAction("Refresh").triggered.connect(lambda: (self.refresh_bots(), self.toast("Bot library refreshed")))
        menu.exec(widget.mapToGlobal(widget.rect().bottomLeft()))

    def import_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Import RLBot V4 / V5 bots", str(Path.home()),
                                                "Bots (*.cfg *.toml *.py *.zip *.7z *.rar *.tar.gz *.tgz);;All files (*)")
        if paths:
            self.queue_import(paths)

    def import_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select RLBot bot directory", str(Path.home()))
        if path:
            self.queue_import([path])

    def import_archive(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose bot archives", str(Path.home()),
                                                "Bot archives (*.zip *.7z *.rar *.tar *.tar.gz *.tgz)")
        if paths:
            self.queue_import(paths)

    def import_urls(self, urls, target_team=None):
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.queue_import(paths, target_team=target_team)

    def queue_import(self, paths, target_team=None):
        if self._busy:
            self.toast("Wait for the current import to finish.", "warning")
            return
        self._busy = True
        names = ", ".join(Path(p).name for p in paths[:2]) + ("…" if len(paths) > 2 else "")
        self.set_loading(f"Importing {names}")
        task = ImportTask(paths)
        self._jobs.append(task)
        task.imported.connect(lambda items, t=target_team: self.import_finished(items, t))
        task.failed.connect(lambda reason: message(
            self, "Import failed", "The bot couldn't be imported.", kind="error", details=reason))
        task.finished.connect(lambda job=task: (self.set_loading(None), self.task_done(job)))
        task.start()

    def set_loading(self, text):
        """Spinner and text in the Bots header while an import runs."""
        if text:
            self.spinner.start()
            self.import_text.setText(text)
            self.status.setText(text + "…")
        else:
            self.spinner.stop()
            self.render_library()

    def task_done(self, task):
        if task in self._jobs:
            self._jobs.remove(task)
        # An archive import can hand off to an installer *before* this signal
        # fires. Never mark the GUI idle while a pip job is still running.
        self._busy = bool(self._install_dialog) or any(x.isRunning() for x in self._jobs)

    def import_finished(self, imported, target_team=None):
        self.refresh_bots()
        if not imported:
            self.notice("No bot.cfg or bot.toml was found in what you dropped.", "No bots found", "warning")
            return
        team = target_team if target_team is not None else self.next_team()
        # Immediate integration: place the first imported bot onto a team.
        first = imported[0]["id"]
        if not any(x.get("id") == first for x in self.setup["players"]):
            self.add_player("bot", team, first)
        self.status.setText(f"Imported {len(imported)} bot(s) into the library")
        self.toast(f"Imported {len(imported)} bot{'s' if len(imported) != 1 else ''}", "success")
        # ImportTask already checked which bots can import their packages.
        # Only ask about the ones that can't, so a re-import never reinstalls.
        requirements = [item for item in imported if item.get("needs_install")]
        warnings = [f"{x['name']}: {x['warning']}" for x in imported if x.get("warning")]
        if warnings:
            message(self, "Compatibility warning", "\n\n".join(warnings[:8]), kind="warning")
        if requirements:
            backend = self.ask_backend(
                "Install bot packages?",
                f"{len(requirements)} imported bot{'s' if len(requirements) != 1 else ''} need extra Python "
                "packages. Installing packages runs code from them, so only continue for bots you trust.",
                "Not now")
            if backend:
                self._install_backend = backend
                self.queue_installs(requirements)

    def queue_installs(self, items):
        queued = {x["path"] for x in self._install_queue}
        self._install_queue.extend(x for x in items if x["path"] not in queued)
        if self._install_dialog is None:
            self.install_next()

    def ask_backend(self, title, text, cancel):
        """CPU or CUDA PyTorch for a package install, or None."""
        return message(self, title, text + "\n\nCPU PyTorch is smaller and works everywhere. "
                       "NVIDIA CUDA is several GB and only helps GPU bots.",
                       buttons=[(cancel, None, ""), ("NVIDIA CUDA", "cuda", ""),
                                ("CPU (recommended)", "cpu", "Primary")])

    def install_next(self):
        if not self._install_queue:
            self._busy = False
            self._install_dialog = None
            return
        item = self._install_queue.pop(0)
        self._busy = True
        task = InstallTask(item["path"], item["requirements"], item["framework"], self._install_backend)
        dialog = ProgressSheet(self, f"Installing packages for {item['name']}", "Resolving dependencies…")
        dialog.canceled.connect(task.requestInterruption)
        self._install_dialog = dialog
        self._jobs.append(task)
        task.progress.connect(lambda message, d=dialog: (
            d.setLabelText(message[:190]) if not d.wasCanceled() else None
        ))
        task.ready.connect(lambda text: (self.status.setText(text),
                                         self.toast(f"Packages installed for {item['name']}", "success")))
        task.failed.connect(lambda error: message(
            self, "Package install failed", f"Packages for {item['name']} couldn't be installed.",
            kind="error", details=error[-6000:]))
        def completed():
            dialog.close()
            if task in self._jobs:
                self._jobs.remove(task)
            self._install_dialog = None
            self._busy = False
            # Keep other bot installs sequential to avoid multiple gigabyte
            # torch downloads running in parallel.
            if self._install_queue:
                self.install_next()
        task.finished.connect(completed)
        dialog.show()
        task.start()

    def manage_bots(self):
        ManageBotsSheet(self).exec()

    def remove_bot(self, bot):
        if not confirm(self, f"Remove {bot['name']}?",
                       "It's removed from the library and from both teams. The bot's files stay on disk.",
                       "Remove", danger=True):
            return False
        lib = [i for i in server._load_library() if i["id"] != bot["id"]]
        server._save_json(server.LIBRARY_FILE, lib)
        self.setup["players"] = [x for x in self.setup["players"] if x.get("id") != bot["id"]]
        if not self.setup["players"]:
            self.setup["players"] = [{"kind": "human", "team": 0}]
        self.refresh_bots()
        self.redraw()
        self.schedule_save()
        self.toast(f"{bot['name']} removed from the library")
        return True

    def configure_game(self):
        d = Sheet(self, "Rocket League location",
                  "Rocket League isn't included. Install it with Heroic and your own Epic account; "
                  "existing Heroic installs are found automatically.", width=720)
        layout = d.body
        info = offline_launcher.installation()
        fields = {}
        for name, key, folder in [
            ("Rocket League folder", "game", True),
            ("Wine prefix folder", "prefix", True),
            ("Heroic Wine executable", "wine", False),
        ]:
            line = QHBoxLayout()
            title = text_label(name, "Key", False)
            title.setFixedWidth(170)
            line.addWidget(title)
            edit = QLineEdit(str(info[key]))
            fields[key] = edit
            line.addWidget(edit, 1)
            browse = QPushButton("Browse…")
            def choose(_, entry=edit, is_folder=folder):
                path = (QFileDialog.getExistingDirectory(d, "Choose directory", entry.text())
                        if is_folder else
                        QFileDialog.getOpenFileName(d, "Choose Wine executable", entry.text())[0])
                if path:
                    entry.setText(path)
            browse.clicked.connect(choose)
            line.addWidget(browse)
            layout.addLayout(line)
        def commit():
            offline_launcher.save_preferences(
                fields["game"].text(), fields["prefix"].text(), fields["wine"].text()
            )
            d.accept()
            self.toast("Rocket League location saved", "success")
        d.add_button("Cancel", result=False)
        d.add_button("Save", "Primary", callback=commit)
        d.exec()

    def install_active_bot_dependencies(self):
        selected = {p.get("id") for p in self.setup["players"] if p.get("kind") == "bot"}
        self.install_bot_dependencies([b for b in self.bots if b["id"] in selected])

    def install_bot_dependencies(self, selected_bots):
        if self._busy:
            self.toast("Wait for the current import or install to finish.", "warning")
            return
        from ui.bot_importer import discover
        from ui.preflight import suggested_requirements, dependencies_ready
        pending = []
        for bot in selected_bots:
            path = Path(bot["path"]).resolve()
            candidates = discover(path)
            chosen = next((c for c in candidates if c.path == path), None)
            if chosen and not dependencies_ready(path, chosen):
                requirement_file = suggested_requirements(path, chosen)
                if requirement_file:
                    pending.append({"path": str(chosen.path), "name": chosen.name,
                                    "framework": chosen.framework,
                                    "requirements": str(requirement_file)})
        if not pending:
            self.notice("Every package these bots need is already installed. If a bot still won't "
                        "start, open Logs or export diagnostics from the menu.", "Nothing to install")
            return
        backend = self.ask_backend(
            "Install bot packages?",
            f"Install Python packages for {len(pending)} bot{'s' if len(pending) != 1 else ''}? "
            "Only install packages for bots you trust.", "Cancel")
        if backend:
            self._install_backend = backend
            self.queue_installs(pending)

    def top_menu(self, widget):
        menu = QMenu(self)
        sections = [("Bots", [("Import bot…", self.import_file),
                              ("Manage bots…", self.manage_bots),
                              ("Install packages for team bots…", self.install_active_bot_dependencies)]),
                    ("Match", [("Reset teams", self.reset_teams),
                               ("Rocket League location…", self.configure_game)]),
                    ("Help", [("Logs", self.show_logs),
                              ("Export diagnostics…", self.export_diagnostics)])]
        for title, entries in sections:
            menu.addSection(title)
            for name, action in entries:
                menu.addAction(name).triggered.connect(action)
        menu.exec(widget.mapToGlobal(widget.rect().bottomLeft()))

    def reset_teams(self):
        previous = [dict(p) for p in self.setup["players"]]
        self.setup["players"] = [{"kind": "human", "team": 0}]
        self.redraw()
        self.schedule_save()

        def undo():
            self.setup["players"] = previous
            self.redraw()
            self.schedule_save()
        self.toast("Teams reset", "info", ("Undo", undo))

    def export_diagnostics(self):
        from ui.support import save_support_zip
        default = Path.home() / "Downloads" / "EvilRLBot-diagnostics.zip"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Evil RLBot diagnostics", str(default),
            "ZIP archive (*.zip)"
        )
        if not filename:
            return
        try:
            output = save_support_zip(Path(filename))
            self.toast("Diagnostics saved. Check them before sharing.", "success",
                       ("Show file", lambda: open_folder(output)))
        except Exception as exc:
            message(self, "Export failed", "The diagnostics file couldn't be written.",
                    kind="error", details=str(exc))

    def show_logs(self):
        from ui.support import collect_logs
        LogsSheet(self, collect_logs(), lambda: open_folder(server.LOG)).exec()

    def _run_background(self, fn, desc):
        if self._busy:
            self.toast("Something is already running. Wait for it to finish.", "warning")
            return
        class ActionThread(QThread):
            ok = Signal(object)
            failed = Signal(str)
            def run(self_inner):
                try:
                    self_inner.ok.emit(fn())
                except Exception as exc:
                    self_inner.failed.emit(str(exc))
        self._busy = True
        self.start.setEnabled(False)
        self.status.setText(desc)
        task = ActionThread(self)
        self._jobs.append(task)
        task.ok.connect(lambda result: self.update_status())
        task.failed.connect(self._operation_failed)
        def ended():
            self._busy = False
            self.start.setEnabled(True)
            if task in self._jobs:
                self._jobs.remove(task)
            self.update_status()
            if self._install_after_failed_match:
                self._install_after_failed_match = False
                QTimer.singleShot(0, self.install_active_bot_dependencies)
        task.finished.connect(ended)
        task.start()

    def _operation_failed(self, error):
        # Do not force users to discover the dependency installer manually after
        # a failed Start Match. Errors still propagate without starting the game.
        if "Bots cannot start:" not in error:
            message(self, "Something went wrong", error.strip().splitlines()[-1][:300] if error.strip() else "Unknown error",
                    kind="error", details=error[-8000:])
            return
        choice = message(
            self, "Bots need Python packages",
            "One or more bots can't import the Python packages they need, so the match didn't start.",
            kind="warning", details=error,
            buttons=[("Close", None, ""), ("Install packages…", "install", "Primary")])
        if choice == "install":
            # Start Match is still finishing its QThread; wait for the finished
            # signal to clear _busy before opening the CPU/CUDA prompt.
            self._install_after_failed_match = True

    def start_match(self):
        self.apply_settings()
        try:
            validated = validate_setup(self.setup, server._bot_paths())
            self.save()
        except Exception as exc:
            self.notice(str(exc), "Can't start the match", "warning")
            return
        self._run_background(lambda: server._start_match(validated), "Starting Rocket League and RLBot V5…")

    def stop_match(self):
        self._run_background(server._stop_match, "Stopping Rocket League…")

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        if self._busy or any(t.isRunning() for t in self._jobs):
            event.ignore()
            self.toast("An import or match operation is still running.", "warning")
            return
        self.save()
        event.accept()


def main():
    # Native Fusion style avoids requiring distro-specific GTK theme plugins.
    app = QApplication(sys.argv)
    app.setApplicationName("Evil RLBot")
    app.setDesktopFileName("evil-rlbot")
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyleSheet(CSS)
    window = ClassicWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
