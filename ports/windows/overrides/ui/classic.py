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
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui import bot_importer, server, offline_launcher
from ui.match_config import validate_setup
from ui.native import MAPS, MODES, LAUNCHERS, MutatorsDialog, OptionsDialog, logo_icon

CSS = """
QMainWindow, QWidget#Main {background:#eceeef; color:#292f33; font:13px 'Noto Sans',Arial,sans-serif}
QWidget {color:#2d3237; font:13px 'Noto Sans',Arial,sans-serif}
QWidget#Content {background:#d9dde1}
QFrame#Header, QFrame#Header * {background:#141517; color:white}
QFrame#WhitePanel {background:#f7f8fa; border:1px solid #c5cdd3; border-radius:4px}
QFrame#Blue {background:#0961ab; border:2px solid #0b518c; border-radius:4px}
QFrame#Orange {background:#ed671c; border:2px solid #cf510c; border-radius:4px}
QLabel#Headline {font:600 17px 'Noto Sans',Arial; color:#202a31}
QLabel#Hint {color:#66717b; font-size:11px}
QLabel#HeaderName {color:#f5f7f8; font:700 21px 'Noto Sans',Arial}
QLabel#OnTeam {color:#fff; font-weight:600; background:transparent}
QPushButton {border:1px solid #bbc4cc; background:#fff; border-radius:4px; color:#2b353e; padding:7px 10px; font-weight:500; min-height:20px}
QPushButton:hover {background:#eef3f8; border-color:#899eae}
QPushButton:pressed {background:#e0e6eb}
QPushButton#HeadButton {background:#343a40; border:1px solid #343a40; color:#fff; padding:8px 13px}
QPushButton#HeadButton:hover {background:#444c54}
QPushButton#Start {background:#28a745; color:#fff; border:1px solid #22943c; font-weight:700; font-size:15px; min-height:34px; padding:9px 22px}
QPushButton#Start:hover {background:#218e3a}
QPushButton#Stop {font-size:14px; min-height:34px; padding:9px 15px}
QPushButton#Filter {border-radius:0; font-size:11px; font-weight:500; padding:4px 10px; color:#1772b9; border:1px solid #1479c7; min-height:18px}
QPushButton#Filter:checked {color:white; background:#237ccb}
QPushButton#BotTile {background:#fff; border:1px solid #d2d8dd; border-radius:4px; padding:7px 9px; text-align:left; font-size:12px; min-width:110px; min-height:23px}
QPushButton#BotTile:hover {background:#edf5ff; border-color:#65a7d6}
QPushButton#Slot {background:#fff; border:1px solid #d3dbe3; border-radius:2px; padding:7px 9px; text-align:left}
QPushButton#SlotRemove {color:#c63c46; background:#fff; border:none; font-size:14px; padding:4px; min-width:20px}
QPushButton#AddTeam {background:transparent; border:none; color:#dceaf5; text-align:left; padding:3px; font-size:12px}
QPushButton#AddTeam:hover {color:#fff; text-decoration:underline}
QLineEdit,QComboBox {background:#fff; border:1px solid #c7d1dc; border-radius:3px; padding:6px 9px; min-height:20px}
QLineEdit:focus,QComboBox:focus {border-color:#1c8de0}
QScrollArea {border:0; background:transparent}
QMenu {background:#fff; border:1px solid #c5cbd0; color:#1d2b39; padding:4px}
QMenu::item {padding:6px 15px}
QMenu::item:selected {background:#dcecf9}
QDialog {background:#f4f5f6}
QPlainTextEdit {background:#fff; color:#222}
QStatusBar {background:#eceeef}
"""

class DragTile(QPushButton):
    def __init__(self, bot, owner):
        super().__init__("◉  " + bot["name"])
        self.owner = owner
        self.bot = bot
        self.setObjectName("BotTile")
        self.setToolTip(f'{bot["name"]}\n{bot["path"]}\n{bot["diagnostics"].get("framework","Unknown")} — drag to a team')
        self.setMaximumWidth(233)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.start_pos = None
        self.clicked.connect(lambda: owner.add_player("bot", owner.next_team(), bot["id"]))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.owner.show_bot_details(self.bot)
            return
        self.start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_pos is not None and (event.pos() - self.start_pos).manhattanLength() > 10 and event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-evilrlbot-bot", self.bot["id"].encode())
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction)
            self.start_pos = None
        else:
            super().mouseMoveEvent(event)


class Team(QFrame):
    def __init__(self, owner, team):
        super().__init__()
        self.owner, self.team = owner, team
        self.setObjectName("Blue" if team == 0 else "Orange")
        self.setAcceptDrops(True)
        col = QVBoxLayout(self)
        col.setContentsMargins(11, 11, 11, 8)
        col.setSpacing(5)
        self.slots = QVBoxLayout()
        self.slots.setSpacing(5)
        col.addLayout(self.slots)
        col.addStretch()
        add = QPushButton("◯  Add to Blue Team" if team == 0 else "◯  Add to Orange Team")
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
        if not players:
            l = QLabel("Drop bots here")
            l.setObjectName("OnTeam")
            l.setStyleSheet("color:#ffffffc8;background:transparent;padding:6px;")
            self.slots.addWidget(l)
        for index, player in players:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            if player["kind"] == "human":
                name = "🎮  Human"
            elif player["kind"] == "psyonix":
                name = "⚙  Psyonix " + player.get("skill", "Pro")
            else:
                found = self.owner.get_bot(player.get("id"))
                name = "⬡  " + (found["name"] if found else "Missing bot")
            title = QPushButton(name)
            title.setObjectName("Slot")
            title.setToolTip("Right click to move to the other team")
            title.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            title.customContextMenuRequested.connect(lambda pos, idx=index, w=title: self.owner.slot_menu(w, pos, idx))
            layout.addWidget(title, 1)
            remove = QPushButton("×")
            remove.setObjectName("SlotRemove")
            remove.setFixedWidth(29)
            remove.setToolTip("Remove player")
            remove.clicked.connect(lambda _, i=index: self.owner.remove_player(i))
            layout.addWidget(remove)
            self.slots.addWidget(row)


class Background(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        from PySide6.QtGui import QPixmap, QLinearGradient
        wallpaper = ROOT / "ui/assets/arena-blur.jpg"
        if wallpaper.exists():
            img = QPixmap(str(wallpaper))
            painter.drawPixmap(self.rect(), img, img.rect())
            painter.fillRect(self.rect(), QColor(0, 0, 0, 40))
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
            self.imported.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


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
        self.setup.setdefault("launcher", "Epic")
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
        top = QWidget()
        top.setObjectName("Main")
        self.setCentralWidget(top)
        outer = QVBoxLayout(top)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(56)
        h = QHBoxLayout(header)
        h.setContentsMargins(15, 5, 18, 5)
        brand = QLabel("⬡  Evil RLBot")
        brand.setObjectName("HeaderName")
        h.addWidget(brand)
        label = QLabel("V4 + V5 ENGINE")
        label.setStyleSheet("color:#bbc3c9;font-size:10px;background:transparent;padding-left:12px")
        h.addWidget(label)
        h.addStretch()
        logs = QPushButton("Logs")
        logs.setObjectName("HeadButton")
        logs.clicked.connect(self.show_logs)
        h.addWidget(logs)
        menu_button = QPushButton("Menu ▾")
        menu_button.setObjectName("HeadButton")
        menu_button.clicked.connect(lambda: self.top_menu(menu_button))
        h.addWidget(menu_button)
        outer.addWidget(header)

        background = Background()
        area = QVBoxLayout(background)
        area.setContentsMargins(20, 10, 20, 10)
        area.setSpacing(12)
        outer.addWidget(background, 1)

        library = QFrame()
        library.setObjectName("WhitePanel")
        self.library_panel = library
        library.setMinimumHeight(205)
        lib = QVBoxLayout(library)
        lib.setContentsMargins(12, 11, 12, 13)
        lib.setSpacing(9)
        controls = QHBoxLayout()
        controls.setSpacing(7)
        controls.addWidget(self.title("Bots"))
        add = QPushButton("＋ Add ▾")
        add.clicked.connect(lambda: self.import_menu(add))
        controls.addWidget(add)
        manage = QPushButton("⚙ Manage bot folders")
        manage.clicked.connect(self.manage_bots)
        controls.addWidget(manage)
        controls.addStretch()
        self.import_text = QLabel("Drag a bot here: ZIP · 7Z · RAR · folder · bot.cfg · bot.toml")
        self.import_text.setObjectName("Hint")
        controls.addWidget(self.import_text)
        lib.addLayout(controls)
        filters = QHBoxLayout()
        filters.setSpacing(0)
        for text in ["All", "Standard", "Extra modes", "Special bots/scripts", "Bots for 1v1", "Bots with teamplay", "Goalie bots"]:
            b = QPushButton(text)
            b.setObjectName("Filter")
            b.setCheckable(True)
            b.setChecked(text == "All")
            b.clicked.connect(lambda checked, name=text: self.set_filter(name))
            filters.addWidget(b)
            setattr(self, "_filter_" + text.replace(" ", "_"), b)
        filters.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search...")
        self.search.setFixedWidth(180)
        self.search.textChanged.connect(self.render_library)
        filters.addWidget(self.search)
        lib.addLayout(filters)
        self.bot_scroll = QScrollArea()
        self.bot_scroll.setWidgetResizable(True)
        self.bot_scroll.setMinimumHeight(110)
        self.bot_content = QWidget()
        self.bot_content.setStyleSheet("background:#f7f8fa")
        self.bot_grid = QGridLayout(self.bot_content)
        self.bot_grid.setContentsMargins(2, 1, 2, 2)
        self.bot_grid.setHorizontalSpacing(7)
        self.bot_grid.setVerticalSpacing(7)
        self.bot_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bot_scroll.setWidget(self.bot_content)
        lib.addWidget(self.bot_scroll, 1)
        area.addWidget(library, 4)

        teams = QHBoxLayout()
        teams.setSpacing(44)
        self.blue = Team(self, 0)
        self.orange = Team(self, 1)
        teams.addWidget(self.blue, 1)
        teams.addWidget(self.orange, 1)
        area.addLayout(teams, 3)

        settings = QFrame()
        settings.setObjectName("WhitePanel")
        settings.setMinimumHeight(142)
        bottom = QVBoxLayout(settings)
        bottom.setContentsMargins(12, 10, 12, 10)
        bottom.setSpacing(7)
        bottom.addWidget(self.title("Match Settings"))
        bar = QHBoxLayout()
        bar.setSpacing(8)
        for title, choices, key in [("Map", MAPS, "map"), ("Mode", MODES, "mode")]:
            field = QVBoxLayout()
            field.setSpacing(3)
            caption = QLabel(title)
            caption.setObjectName("Hint")
            field.addWidget(caption)
            combo = QComboBox()
            for name, val in choices:
                combo.addItem(name, val)
            combo.currentIndexChanged.connect(self.apply_settings)
            setattr(self, key + "_combo", combo)
            field.addWidget(combo)
            bar.addLayout(field)
        for caption, callback in [("Mutators", self.show_mutators), ("Extra", self.show_extra)]:
            bar.addWidget(QPushButton(caption, clicked=callback), 0, Qt.AlignmentFlag.AlignBottom)
        bar.addStretch()
        self.launcher_combo = QComboBox()
        for name, value in LAUNCHERS:
            self.launcher_combo.addItem(name, value)
        self.launcher_combo.currentIndexChanged.connect(self.apply_settings)
        self.launcher_combo.setFixedWidth(200)
        bar.addWidget(self.launcher_combo, 0, Qt.AlignmentFlag.AlignBottom)
        self.start = QPushButton("Start Match")
        self.start.setObjectName("Start")
        self.start.clicked.connect(self.start_match)
        bar.addWidget(self.start, 0, Qt.AlignmentFlag.AlignBottom)
        stop = QPushButton("Stop")
        stop.setObjectName("Stop")
        stop.clicked.connect(self.stop_match)
        bar.addWidget(stop, 0, Qt.AlignmentFlag.AlignBottom)
        bottom.addLayout(bar)
        notes = QHBoxLayout()
        self.status = QLabel("Ready")
        self.status.setObjectName("Hint")
        notes.addWidget(self.status)
        notes.addStretch()
        notes.addWidget(QLabel("RLBot v5 engine · V4 compatibility bridge"))
        bottom.addLayout(notes)
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
        col_count = max(2, min(8, (max(650, self.library_panel.width()) - 40) // 168))
        for index, b in enumerate(bots):
            self.bot_grid.addWidget(DragTile(b, self), index // col_count, index % col_count)
        for index in range(col_count):
            self.bot_grid.setColumnStretch(index, 1)
        self.import_text.setText(f"{len(self.bots)} bots · Drop ZIP, RAR, 7Z, folder, CFG or TOML to import")

    def next_team(self):
        blue = sum(x["team"] == 0 for x in self.setup["players"])
        orange = sum(x["team"] == 1 for x in self.setup["players"])
        return 0 if blue <= orange else 1

    def add_player(self, kind, team, value=None):
        if len(self.setup["players"]) >= 10:
            self.notice("Rocket League supports a maximum of 10 players in this setup.")
            return
        if kind == "human" and any(x["kind"] == "human" for x in self.setup["players"]):
            self.notice("One local human is supported in this launcher.")
            return
        if kind == "bot" and not self.get_bot(value):
            self.notice("Please import this bot first.")
            return
        player = {"kind": kind, "team": team}
        if kind == "bot":
            player["id"] = value
        if kind == "psyonix":
            player["skill"] = value or "Pro"
        self.setup["players"].append(player)
        self.redraw()
        self.schedule_save()

    def remove_player(self, index):
        if len(self.setup["players"]) <= 1:
            self.notice("At least one player is required.")
            return
        self.setup["players"].pop(index)
        self.redraw()
        self.schedule_save()

    def slot_menu(self, source, pos, index):
        menu = QMenu(self)
        action = menu.addAction("Move to other team")
        action.triggered.connect(lambda: self.move_player(index))
        menu.exec(source.mapToGlobal(pos))

    def move_player(self, index):
        self.setup["players"][index]["team"] = 1 - self.setup["players"][index]["team"]
        self.redraw()
        self.schedule_save()

    def add_menu(self, button_widget, team):
        menu = QMenu(self)
        for title, kind, val in [("Human", "human", None), ("Psyonix Rookie", "psyonix", "Rookie"),
                                 ("Psyonix Pro", "psyonix", "Pro"), ("Psyonix Allstar", "psyonix", "Allstar")]:
            act = menu.addAction(title)
            act.triggered.connect(lambda _, k=kind, v=val: self.add_player(k, team, v))
        menu.addSeparator()
        for bot in self.bots:
            act = menu.addAction(bot["name"])
            act.triggered.connect(lambda _, id=bot["id"]: self.add_player("bot", team, id))
        menu.exec(button_widget.mapToGlobal(button_widget.rect().bottomLeft()))

    def redraw(self):
        for key, default in [("map", "Stadium_P"), ("mode", "Soccar"), ("launcher", "Epic")]:
            combo = getattr(self, key + "_combo")
            combo.blockSignals(True)
            i = combo.findData(self.setup.get(key, default))
            if i >= 0:
                combo.setCurrentIndex(i)
            combo.blockSignals(False)
        self.blue.redraw()
        self.orange.redraw()

    def apply_settings(self, *_):
        self.setup["map"] = self.map_combo.currentData()
        self.setup["mode"] = self.mode_combo.currentData()
        self.setup["launcher"] = self.launcher_combo.currentData()
        self.schedule_save()

    def show_mutators(self):
        dlg = MutatorsDialog(self, self.setup)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.setup["mutators"] = dlg.values()
            self.schedule_save()

    def show_extra(self):
        dlg = OptionsDialog(self, self.setup)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.setup["options"] = dlg.values()
            self.schedule_save()

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
            self.status.setStyleSheet("color:#66717b")
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
            self.status.setStyleSheet("color:#ad2525;font-weight:600")
            return
        counts = re.findall(r"Agents ready:\s*(\d+)\s*/\s*(\d+)", tail)
        if counts:
            count, total = map(int, counts[-1])
            if count < total:
                self.status.setText(f"◌ Initializing bots: {count}/{total}")
                self.status.setStyleSheet("color:#9a6800")
                return
            self.status.setText(f"● Match running — {count}/{total} bots ready")
        else:
            self.status.setText("◌ Starting game and loading bots…")
        self.status.setStyleSheet("color:#427047")

    def notice(self, message):
        QMessageBox.information(self, "Evil RLBot", message)

    def show_bot_details(self, bot):
        report = bot.get("diagnostics", {})
        info = f"Bot: {bot['name']}\nFile: {bot['path']}\nFramework: {report.get('framework','unknown')}\n"
        info += f"Observation: {report.get('observation','unknown')}\n"
        info += f"Runtime: {report.get('model_runtime','unknown')}\n\n"
        info += "\n".join(report.get("warnings", []))
        self.notice(info)

    def import_menu(self, widget):
        menu = QMenu(self)
        actions = [
            ("Import bot file…", self.import_file), ("Import folder…", self.import_folder),
            ("Import ZIP / RAR / 7Z archive…", self.import_archive),
            ("Refresh bot library", self.refresh_bots),
        ]
        for name, callback in actions:
            action = menu.addAction(name)
            action.triggered.connect(callback)
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
            self.notice("Wait for the current import to finish.")
            return
        self._busy = True
        self.status.setText(f"Importing {len(paths)} item(s)…")
        task = ImportTask(paths)
        self._jobs.append(task)
        task.imported.connect(lambda items, t=target_team: self.import_finished(items, t))
        task.failed.connect(lambda reason: self.notice("Import failed: " + reason))
        task.finished.connect(lambda job=task: self.task_done(job))
        task.start()

    def task_done(self, task):
        if task in self._jobs:
            self._jobs.remove(task)
        # An archive import can hand off to an installer *before* this signal
        # fires. Never mark the GUI idle while a pip job is still running.
        self._busy = bool(self._install_dialog) or any(x.isRunning() for x in self._jobs)

    def import_finished(self, imported, target_team=None):
        self.refresh_bots()
        if not imported:
            self.notice("No RLBot bots found in the dropped files.")
            return
        team = target_team if target_team is not None else self.next_team()
        # Immediate integration: place the first imported bot onto a team.
        first = imported[0]["id"]
        if not any(x.get("id") == first for x in self.setup["players"]):
            self.add_player("bot", team, first)
        self.status.setText(f"Imported {len(imported)} bot(s) into the library")
        # A bot may already have a verified per-bot environment from a prior
        # installation (or a locally reusable dependency set). Never reinstall
        # 5+ GiB of Torch when its environment is already prepared.
        from ui.preflight import dependencies_ready
        requirements = []
        for item in imported:
            if not item.get("requirements") or not item.get("new"):
                continue
            candidates = bot_importer.discover(Path(item["path"]))
            chosen = next((c for c in candidates if c.path == Path(item["path"])), None)
            if chosen and not dependencies_ready(chosen.path, chosen):
                requirements.append(item)
        warnings = [f"{x['name']}: {x['warning']}" for x in imported if x.get("warning")]
        if warnings:
            QMessageBox.warning(self, "Bot compatibility warning", "\n".join(warnings[:8]))
        if requirements:
            prompt = QMessageBox(self)
            prompt.setWindowTitle("Install bot dependencies?")
            prompt.setIcon(QMessageBox.Icon.Question)
            prompt.setText(
                f"{len(requirements)} imported bot(s) require additional Python packages.\n"
                "Installing packages can execute code; only approve bots you trust.\n\n"
                "CPU PyTorch is smaller and more portable (recommended). "
                "NVIDIA CUDA can be several GB and is useful only for GPU-compatible bots. "
                "Which version should Evil RLBot install?"
            )
            cpu = prompt.addButton("CPU (recommended)", QMessageBox.ButtonRole.AcceptRole)
            cuda = prompt.addButton("NVIDIA CUDA (large)", QMessageBox.ButtonRole.AcceptRole)
            prompt.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
            prompt.exec()
            selected = prompt.clickedButton()
            if selected in (cpu, cuda):
                self._install_backend = "cuda" if selected is cuda else "cpu"
                self._install_queue = list(requirements)
                self.install_next()

    def install_next(self):
        if not self._install_queue:
            self._busy = False
            self._install_dialog = None
            return
        item = self._install_queue.pop(0)
        self._busy = True
        task = InstallTask(item["path"], item["requirements"], item["framework"], self._install_backend)
        dialog = QProgressDialog(f"Resolving {item['name']} dependencies…", "Cancel", 0, 0, self)
        dialog.setWindowTitle("Installing bot packages — Evil RLBot")
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setMinimumWidth(520)
        dialog.setMinimumDuration(250)
        dialog.setAutoReset(False)
        dialog.setAutoClose(False)
        dialog.canceled.connect(task.requestInterruption)
        self._install_dialog = dialog
        self._jobs.append(task)
        task.progress.connect(lambda message, d=dialog: (
            d.setLabelText(message[:190]) if not d.wasCanceled() else None
        ))
        task.ready.connect(lambda message: self.status.setText(message))
        task.failed.connect(lambda error: QMessageBox.warning(
            self, "Bot dependency installation failed", error[-2300:]
        ))
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
        text = "Imported bot files:\n\n" + "\n".join(f"{b['name']}  —  {b['path']}" for b in self.bots)
        d = QDialog(self)
        d.setWindowTitle("Manage bot folders")
        d.resize(720, 400)
        v = QVBoxLayout(d)
        desc = QLabel("Bots are kept in the library, archives are unpacked in ~/.local/share/evilrlbot/bots/")
        v.addWidget(desc)
        editor = QPlainTextEdit(text)
        editor.setReadOnly(True)
        v.addWidget(editor)
        footer = QHBoxLayout()
        footer.addWidget(QPushButton("Import new…", clicked=self.import_file))
        footer.addWidget(QPushButton("Remove selected bot…", clicked=self.remove_bot_dialog))
        footer.addWidget(QPushButton("Close", clicked=d.accept))
        v.addLayout(footer)
        d.exec()

    def remove_bot_dialog(self):
        menu = QMenu(self)
        for bot in self.bots:
            a = menu.addAction(bot["name"])
            a.triggered.connect(lambda _, b=bot: self.remove_bot(b))
        menu.exec(self.mapToGlobal(self.rect().center()))

    def remove_bot(self, bot):
        if QMessageBox.question(self, "Remove bot", f"Remove {bot['name']} from library?\nThe bot's files will not be deleted.") != QMessageBox.StandardButton.Yes:
            return
        lib = [i for i in server._load_library() if i["id"] != bot["id"]]
        server._save_json(server.LIBRARY_FILE, lib)
        self.setup["players"] = [x for x in self.setup["players"] if x.get("id") != bot["id"]]
        if not self.setup["players"]:
            self.setup["players"] = [{"kind": "human", "team": 0}]
        self.refresh_bots()
        self.redraw()
        self.schedule_save()

    def configure_game(self):
        d = QDialog(self)
        d.setWindowTitle("Configure Rocket League — Evil RLBot")
        d.resize(720, 350)
        layout = QVBoxLayout(d)
        intro = QLabel(
            "The AppImage includes RLBot V4/V5 but NOT Rocket League. "
            "For Legendary Offline, install Heroic and sign in to your own Epic account. "
            "Existing Heroic game installations are detected automatically."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        info = offline_launcher.installation()
        fields = {}
        for name, key, folder in [
            ("Rocket League folder", "game", True),
            ("Wine prefix folder", "prefix", True),
            ("Heroic Wine executable", "wine", False),
        ]:
            line = QHBoxLayout()
            title = QLabel(name)
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
        layout.addStretch()
        buttons = QHBoxLayout()
        save = QPushButton("Save")
        save.setObjectName("Start")
        def commit():
            offline_launcher.save_preferences(
                fields["game"].text(), fields["prefix"].text(), fields["wine"].text()
            )
            d.accept()
            self.status.setText("Rocket League configuration saved")
        save.clicked.connect(commit)
        buttons.addStretch()
        buttons.addWidget(QPushButton("Cancel", clicked=d.reject))
        buttons.addWidget(save)
        layout.addLayout(buttons)
        d.exec()

    def install_active_bot_dependencies(self):
        if self._busy:
            self.notice("Wait for the current import or installation to finish.")
            return
        selected = {p.get("id") for p in self.setup["players"] if p.get("kind") == "bot"}
        selected_bots = [b for b in self.bots if b["id"] in selected]
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
            self.notice(
                "No missing installable Python packages were found for the selected bots. "
                "Dependencies are already available, or the bot has another startup problem. "
                "Use Menu → Export Diagnostics for details."
            )
            return
        prompt = QMessageBox(self)
        prompt.setWindowTitle("Install dependencies for selected bots?")
        prompt.setIcon(QMessageBox.Icon.Question)
        prompt.setText(
            f"Install/reinstall Python dependencies for {len(pending)} selected bot(s)?\n"
            "Only install trusted packages. CPU Torch downloads are smaller; "
            "some GPU bots require NVIDIA CUDA support."
        )
        cpu = prompt.addButton("CPU (recommended)", QMessageBox.ButtonRole.AcceptRole)
        cuda = prompt.addButton("NVIDIA CUDA", QMessageBox.ButtonRole.AcceptRole)
        prompt.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        prompt.exec()
        selected_button = prompt.clickedButton()
        if selected_button in (cpu, cuda):
            self._install_backend = "cuda" if selected_button is cuda else "cpu"
            self._install_queue = pending
            self.install_next()

    def top_menu(self, widget):
        menu = QMenu(self)
        for name, action in [("Import bot…", self.import_file),
                             ("Install bot dependencies…", self.install_active_bot_dependencies),

                             ("Match logs", self.show_logs),
                             ("Export Diagnostics…", self.export_diagnostics),
                             ("Manage bot folders", self.manage_bots),
                             ("Reset teams", self.reset_teams)]:
            item = menu.addAction(name)
            item.triggered.connect(action)
        menu.exec(widget.mapToGlobal(widget.rect().bottomLeft()))

    def reset_teams(self):
        self.setup["players"] = [{"kind": "human", "team": 0}]
        self.redraw()
        self.schedule_save()

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
            self.notice(
                f"Support report saved:\n{output}\n\n"
                "Review contents before sending it. It includes bot and pip errors "
                "but excludes private Epic launcher logs."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def show_logs(self):
        d = QDialog(self)
        d.setWindowTitle("Evil RLBot — Match logs")
        d.resize(880, 550)
        v = QVBoxLayout(d)
        output = QPlainTextEdit()
        output.setReadOnly(True)
        from ui.support import collect_logs
        logs = collect_logs()
        data = "\n\n".join(f"=== {name} ===\n{contents[-25000:]}" for name,contents in logs.items())
        output.setPlainText(data if data else "No RLBot or Python dependency logs yet.")
        v.addWidget(output)
        v.addWidget(QPushButton("Close", clicked=d.accept))
        d.exec()

    def _run_background(self, fn, desc):
        if self._busy:
            self.notice("An operation is already running.")
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

    def _operation_failed(self, message):
        # Do not force users to discover the dependency installer manually after
        # a failed Start Match. Errors still propagate without starting the game.
        if "Bots cannot start:" not in message:
            QMessageBox.warning(self, "Evil RLBot", message[-4500:])
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Bots need Python dependencies")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(
            "One or more bots failed to load their required Python packages.\n"
            "Evil RLBot checks host Python installations first; if no compatible "
            "runtime is found, only the missing dependencies need installation."
        )
        dialog.setDetailedText(message)
        install = dialog.addButton(
            "Install missing bot packages…", QMessageBox.ButtonRole.AcceptRole
        )
        dialog.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is install:
            # Start Match is still finishing its QThread; wait for the finished
            # signal to clear _busy before opening the CPU/CUDA prompt.
            self._install_after_failed_match = True

    def start_match(self):
        self.apply_settings()
        try:
            validated = validate_setup(self.setup, server._bot_paths())
            self.save()
        except Exception as exc:
            self.notice(str(exc))
            return
        self._run_background(lambda: server._start_match(validated), "Starting Rocket League and RLBot V5…")

    def stop_match(self):
        self._run_background(server._stop_match, "Stopping Rocket League…")

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        if self._busy or any(t.isRunning() for t in self._jobs):
            event.ignore()
            self.notice("An import or match operation is still running. Please wait.")
            return
        self.save()
        event.accept()


def main():
    # Native Fusion style avoids requiring distro-specific GTK theme plugins.
    app = QApplication(sys.argv)
    app.setApplicationName("Evil RLBot")
    app.setDesktopFileName("evil-rlbot")
    app.setStyle("Fusion")
    app.setStyleSheet(CSS)
    window = ClassicWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
