#!/usr/bin/env python3
"""Evil RLBot native desktop application (Qt Widgets, no embedded browser).

Maintains the familiar RLBot workflow and reuses the proven RLBot v5 match
composer and exact RLBot v4 bridge, without an HTTP server or browser.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QDrag, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui import server as backend
from ui.match_config import DEFAULT_MUTATORS, DEFAULT_OPTIONS, MUTATORS, validate_setup
from ui.game_status import inspect_game, explain_game_status


MAPS = [
    ("DFH Stadium", "Stadium_P"),
    ("Mannfield", "EuroStadium_P"),
    ("Urban Central", "TrainStation_P"),
    ("Utopia Coliseum", "UtopiaStadium_P"),
    ("Dunk House", "HoopsStadium_P"),
    ("Labs Utopia", "Labs_Utopia_P"),
    ("Beckwith Park", "Park_P"),
    ("Underpass", "Underpass_P"),
]
LAUNCHERS = [
    ("Epic Games / Rocket League", "Epic"),
    ("Steam / Rocket League", "Steam"),
    ("Already running / No launch", "NoLaunch"),
]

MODES = [("Soccar", "Soccar"), ("Hoops", "Hoops"), ("Dropshot", "Dropshot"),
         ("Snow Day", "Snowday"), ("Rumble", "Rumble"), ("Heatseeker", "Heatseeker")]
MUTATOR_TITLES = {
    "match_length": "Match length", "max_score": "Max score",
    "overtime": "Overtime", "series_length": "Series length",
    "game_speed": "Game speed", "ball_max_speed": "Ball max speed",
    "ball_type": "Ball type", "ball_weight": "Ball weight",
    "ball_size": "Ball size", "ball_bounciness": "Ball bounciness",
    "boost_amount": "Boost amount", "boost_strength": "Boost strength",
    "rumble": "Rumble", "gravity": "Gravity", "demolish": "Demolitions",
    "respawn_time": "Respawn time",
}
MUTATOR_LABELS = {
    "FiveMinutes": "5 minutes", "TenMinutes": "10 minutes", "TwentyMinutes": "20 minutes",
    "OneGoal": "1 goal", "ThreeGoals": "3 goals", "FiveGoals": "5 goals",
    "ThreeGames": "3 games", "FiveGames": "5 games", "SevenGames": "7 games",
    "FiveMaxFirstScore": "+5 max, first score", "FiveMaxRandomTeam": "+5 max, random team",
    "SloMo": "Slow motion", "TimeWarp": "Time warp", "SuperFast": "Super fast",
    "SuperLight": "Super light", "SuperHigh": "Super high",
    "NormalBoost": "Normal", "UnlimitedBoost": "Unlimited boost",
    "SlowRecharge": "Slow recharge", "RapidRecharge": "Fast recharge", "NoBoost": "No boost",
    "DefaultRumble": "Default rumble", "DestructionDerby": "Destruction Derby",
    "SpringLoaded": "Spring Loaded", "SpikesOnly": "Spikes only",
    "SpikeRush": "Spike Rush", "One": "1×", "OneAndAHalf": "1.5×",
    "Two": "2×", "Ten": "10×", "FriendlyFire": "Friendly fire",
    "OnContact": "On contact", "OnContactFf": "On contact (friendly fire)",
    "ThreeSeconds": "3 seconds", "TwoSeconds": "2 seconds",
    "OneSecond": "1 second", "DisableGoalReset": "No goal reset",
}
OPTION_TITLES = {
    "skip_replays": "Skip goal replays", "instant_start": "Instant start",
    "enable_rendering": "Allow bot rendering", "enable_state_setting": "Allow game state setting",
    "auto_save_replay": "Automatically save replay",
}

QSS = """
QWidget { color:#e5edf8; font-family:Inter, 'Noto Sans', sans-serif; font-size:13px; }
QMainWindow, QWidget#Root { background:#0a101a; }
QFrame#Sidebar { background:#111a29; border-right:1px solid #25354d; }
QFrame#Panel { background:#131f30; border:1px solid #2b3b54; border-radius:10px; }
QFrame#BluePanel { background:#111d2d; border:2px solid #2081d7; border-radius:10px; }
QFrame#OrangePanel { background:#181c2a; border:2px solid #e87924; border-radius:10px; }
QFrame#PlayerSlot { background:#223047; border:1px solid #344965; border-radius:7px; }
QLabel#Title { font-size:23px; font-weight:800; color:#f7fbff; }
QLabel#Heading { font-size:16px; font-weight:750; color:#f2f7ff; }
QLabel#Muted { color:#9cacbf; }
QLabel#BlueHeading { color:#78bfff; font-weight:800; font-size:14px; }
QLabel#OrangeHeading { color:#ffad6c; font-weight:800; font-size:14px; }
QPushButton { background:#23334a; color:#e5efff; border:1px solid #39506d; padding:8px 12px; border-radius:7px; font-weight:600; }
QPushButton:hover { background:#304661; border-color:#54749b; }
QPushButton:pressed { background:#182438; }
QPushButton:disabled { color:#69798f; background:#192334; }
QPushButton#Primary { background:#0d9048; border:1px solid #24b76c; color:white; font-size:14px; font-weight:800; }
QPushButton#Primary:hover { background:#11a354; }
QPushButton#Danger { background:#972638; border:1px solid #d04353; color:white; }
QPushButton#Danger:hover { background:#b03045; }
QPushButton#BlueAction { background:#1c4b7d; border:1px solid #327abf; }
QPushButton#OrangeAction { background:#724425; border:1px solid #dc7426; }
QPushButton#Nav { background:transparent; border:none; border-radius:8px; padding:13px; text-align:left; font-size:14px; }
QPushButton#Nav:checked { background:#1b493a; color:#b5f7d0; border-left:3px solid #31d37b; }
QLineEdit,QComboBox,QPlainTextEdit,QListWidget { background:#101a2a; border:1px solid #344962; border-radius:7px; padding:7px; selection-background-color:#216f57; }
QListWidget::item { border-bottom:1px solid #25354a; padding:10px 5px; }
QListWidget::item:selected { background:#244262; border-radius:5px; }
QComboBox::drop-down { border:0px; width:24px; }
QScrollArea { background:#0a101a; border:0px; }
QWidget#NativeScrollBody { background:#0a101a; }
QScrollBar:vertical { background:#0d1624; width:10px; }
QScrollBar::handle:vertical { background:#32455c; border-radius:4px; }
QDialog { background:#101a29; }
QToolTip { background:#223047; color:white; border:1px solid #54708b; }
"""


def label(text: str, role: str = "", *, wrap: bool = False):
    result = QLabel(text)
    if role:
        result.setObjectName(role)
    result.setWordWrap(wrap)
    return result


def button(text: str, callback, role: str = "", tip: str = ""):
    result = QPushButton(text)
    if role:
        result.setObjectName(role)
    if tip:
        result.setToolTip(tip)
    result.clicked.connect(callback)
    return result


def vertical(parent=None, gap=9, margins=(0, 0, 0, 0)):
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(*margins)
    layout.setSpacing(gap)
    return layout


def horizontal(parent=None, gap=8, margins=(0, 0, 0, 0)):
    layout = QHBoxLayout(parent)
    layout.setContentsMargins(*margins)
    layout.setSpacing(gap)
    return layout


def logo_icon():
    """The Evil RLBot shield, with sharp versions for small sizes."""
    source = QPixmap(str(Path(__file__).resolve().parent / "assets" / "logo.png"))
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
    return icon


class Worker(QThread):
    success = Signal(object)
    failed = Signal(str)

    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target

    def run(self):
        try:
            result = self.target()
            self.success.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class BotList(QListWidget):
    dropped_file = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if not item:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-evilrlbot-bot", str(item.data(Qt.ItemDataRole.UserRole)).encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class TeamPanel(QFrame):
    def __init__(self, owner, team):
        super().__init__()
        self.owner = owner
        self.team = team
        self.setObjectName("BluePanel" if team == 0 else "OrangePanel")
        self.setAcceptDrops(True)
        layout = vertical(self, margins=(13, 13, 13, 13))
        head = horizontal()
        head.addWidget(label("BLUE TEAM" if team == 0 else "ORANGE TEAM",
                             "BlueHeading" if team == 0 else "OrangeHeading"))
        head.addStretch()
        self.count = label("0 PLAYERS", "Muted")
        head.addWidget(self.count)
        layout.addLayout(head)
        self.slots = vertical(gap=7)
        layout.addLayout(self.slots)
        layout.addStretch()
        foot = horizontal()
        foot.addWidget(button("＋ Selected bot", lambda: owner.add_selected_bot(team)))
        foot.addWidget(button("＋ Psyonix", lambda: owner.add_player("psyonix", team, "Pro")))
        layout.addLayout(foot)
        self.setMinimumHeight(190)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-evilrlbot-bot"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-evilrlbot-bot"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-evilrlbot-bot"):
            bot_id = bytes(event.mimeData().data("application/x-evilrlbot-bot")).decode("utf-8")
            self.owner.add_player("bot", self.team, bot_id)
            event.acceptProposedAction()

    def redraw(self):
        players = [(i, p) for i, p in enumerate(self.owner.setup["players"]) if p["team"] == self.team]
        self.count.setText(f"{len(players)} PLAYER{'S' if len(players) != 1 else ''}")
        while self.slots.count():
            item = self.slots.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        if not players:
            empty = label("Drag bots here or add players above", "Muted")
            empty.setMinimumHeight(70)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.slots.addWidget(empty)
        for index, player in players:
            box = QFrame()
            box.setObjectName("PlayerSlot")
            line = horizontal(box, gap=7, margins=(9, 7, 9, 7))
            if player["kind"] == "human":
                title, meta = "🎮 Human", "Local player"
            elif player["kind"] == "psyonix":
                title, meta = "🤖 Psyonix " + player.get("skill", "Pro"), "Rocket League AI"
            else:
                found = self.owner.bot_by_id(player.get("id"))
                title = "🤖 " + (found.get("name", "Bot") if found else "Missing bot")
                meta = found.get("diagnostics", {}).get("framework", "RLBot") if found else "Missing"
            text_col = vertical(gap=0)
            name = label(title)
            name.setStyleSheet("font-weight:700;")
            name.setToolTip(title)
            sub = label(meta, "Muted")
            text_col.addWidget(name)
            text_col.addWidget(sub)
            line.addLayout(text_col, 1)
            for text, cb, tip in [
                ("⇄", lambda _, i=index: self.owner.swap_player(i), "Switch teams"),
                ("＋", lambda _, i=index: self.owner.duplicate_player(i), "Duplicate player"),
                ("×", lambda _, i=index: self.owner.remove_player(i), "Remove player"),
            ]:
                b = button(text, cb, tip=tip)
                b.setFixedWidth(32)
                b.setFixedHeight(30)
                line.addWidget(b)
            self.slots.addWidget(box)


class MutatorsDialog(QDialog):
    def __init__(self, parent, setup):
        super().__init__(parent)
        self.setWindowTitle("Match mutators — Evil RLBot")
        self.setMinimumSize(740, 600)
        main = vertical(self, gap=12, margins=(20, 18, 20, 18))
        main.addWidget(label("Match Mutators", "Heading"))
        main.addWidget(label("The same RLBot match options, running on the V5 engine.", "Muted"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(4, 5, 10, 10)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(16)
        self.controls = {}
        for index, key in enumerate(MUTATOR_TITLES):
            cell = QWidget()
            column = vertical(cell, gap=5)
            column.addWidget(label(MUTATOR_TITLES[key], "Muted"))
            cb = QComboBox()
            for val in sorted(MUTATORS[key], key=lambda x: (x != "Default", x != "Unlimited", x)):
                cb.addItem(MUTATOR_LABELS.get(val, val), val)
            current = setup.get("mutators", {}).get(key, DEFAULT_MUTATORS[key])
            cb.setCurrentIndex(max(0, cb.findData(current)))
            column.addWidget(cb)
            grid.addWidget(cell, index // 2, index % 2)
            self.controls[key] = cb
        scroll.setWidget(body)
        main.addWidget(scroll, 1)
        foot = horizontal()
        foot.addWidget(button("Reset defaults", self.reset))
        foot.addStretch()
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(self.accept)
        btn.rejected.connect(self.reject)
        foot.addWidget(btn)
        main.addLayout(foot)

    def reset(self):
        for key, combo in self.controls.items():
            combo.setCurrentIndex(combo.findData(DEFAULT_MUTATORS[key]))

    def values(self):
        return {key: control.currentData() for key, control in self.controls.items()}


class OptionsDialog(QDialog):
    def __init__(self, parent, setup):
        super().__init__(parent)
        self.setWindowTitle("Extra match settings")
        self.setMinimumWidth(440)
        layout = vertical(self, margins=(22, 22, 22, 22), gap=12)
        layout.addWidget(label("Extra match settings", "Heading"))
        self.checks = {}
        for key, title in OPTION_TITLES.items():
            cb = QCheckBox(title)
            cb.setChecked(bool(setup.get("options", {}).get(key, DEFAULT_OPTIONS[key])))
            layout.addWidget(cb)
            self.checks[key] = cb
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(self.accept)
        btn.rejected.connect(self.reject)
        layout.addWidget(btn)

    def values(self):
        return {key: cb.isChecked() for key, cb in self.checks.items()}


class NativeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evil RLBot — Native Match Setup")
        self.setWindowIcon(logo_icon())
        self.resize(1380, 870)
        self.setMinimumSize(1020, 680)
        self.bots = []
        self.setup = backend._load_setup()
        self.setup.setdefault("mutators", dict(DEFAULT_MUTATORS))
        self.setup.setdefault("options", dict(DEFAULT_OPTIONS))
        self.worker = None
        self.busy = False
        self.last_status = None
        self.updating = False
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(420)
        self.save_timer.timeout.connect(self.save_setup)
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1500)
        self.status_timer.timeout.connect(self.update_status)
        self.log_timer = QTimer(self)
        self.log_timer.setInterval(1000)
        self.log_timer.timeout.connect(self.read_logs)
        self._build()
        self.refresh_bots()
        self.redraw()
        self.status_timer.start()
        self.update_status()

    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        top = horizontal(root, gap=0)

        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(218)
        rail = vertical(side, gap=8, margins=(15, 22, 15, 18))
        brand = horizontal(gap=8)
        logo = QLabel()
        logo.setPixmap(logo_icon().pixmap(38, 38))
        brand.addWidget(logo)
        titles = vertical(gap=1)
        titles.addWidget(label("Evil RLBot", "Heading"))
        titles.addWidget(label("NATIVE · V5 ENGINE", "Muted"))
        brand.addLayout(titles)
        rail.addLayout(brand)
        rail.addSpacing(27)
        self.nav_buttons = []
        for i, (name, icon) in enumerate([
            ("Match Setup", "⚔"), ("Bot Library", "🤖"),
            ("Match Logs", "≡"), ("About", "ⓘ"),
        ]):
            b = button(f"{icon}   {name}", lambda _, index=i: self.navigate(index), "Nav")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setMinimumHeight(45)
            self.nav_buttons.append(b)
            rail.addWidget(b)
        rail.addStretch()
        rail.addWidget(label("RLBot V4 compatibility", "Muted"))
        rail.addWidget(label("Native RLBot V5 server", "Muted"))
        rail.addWidget(label("Linux · Fedora", "Muted"))
        top.addWidget(side)

        content = QWidget()
        main = vertical(content, gap=13, margins=(25, 20, 25, 17))
        banner = horizontal()
        heading = vertical(gap=2)
        heading.addWidget(label("Match Setup", "Title"))
        heading.addWidget(label("Real V4 bots · native V5 engine · Qt desktop interface", "Muted"))
        banner.addLayout(heading)
        banner.addStretch()
        self.global_status = label("● Idle", "Muted")
        banner.addWidget(self.global_status)
        main.addLayout(banner)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._match_page())
        self.stack.addWidget(self._library_page())
        self.stack.addWidget(self._logs_page())
        self.stack.addWidget(self._about_page())
        main.addWidget(self.stack, 1)
        top.addWidget(content, 1)

    def _match_page(self):
        widget = QWidget()
        outer = horizontal(widget, gap=16)

        library = QFrame()
        library.setObjectName("Panel")
        library.setFixedWidth(315)
        left = vertical(library, margins=(13, 15, 13, 14), gap=10)
        bar = horizontal()
        bar.addWidget(label("Bot Library", "Heading"))
        bar.addStretch()
        bar.addWidget(button("＋", self.import_file, tip="Import bot.cfg, bot.toml or Python bot"))
        left.addLayout(bar)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search installed bots...")
        self.search.textChanged.connect(self.filter_bots)
        left.addWidget(self.search)
        self.filter = QComboBox()
        for name in ["All", "Standard", "ML", "Favorites"]:
            self.filter.addItem(name)
        self.filter.currentIndexChanged.connect(self.filter_bots)
        left.addWidget(self.filter)
        self.bot_list = BotList()
        self.bot_list.itemSelectionChanged.connect(self.on_bot_select)
        self.bot_list.itemDoubleClicked.connect(lambda _: self.add_selected_bot(self.next_team()))
        left.addWidget(self.bot_list, 1)
        actions = horizontal()
        actions.addWidget(button("＋ Blue", lambda: self.add_selected_bot(0), "BlueAction"))
        actions.addWidget(button("＋ Orange", lambda: self.add_selected_bot(1), "OrangeAction"))
        left.addLayout(actions)
        actions = horizontal()
        actions.addWidget(button("★ Favorite", self.toggle_favorite))
        actions.addWidget(button("ⓘ Info", self.selected_diagnostics))
        left.addLayout(actions)
        actions = horizontal()
        actions.addWidget(button("Import folder…", self.import_folder))
        actions.addWidget(button("↻", self.refresh_bots, tip="Refresh bot library"))
        left.addLayout(actions)
        self.bot_details = label("Select a bot or import one.", "Muted", wrap=True)
        left.addWidget(self.bot_details)
        outer.addWidget(library)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea {background:#0a101a; border:0;}')
        scroll.viewport().setStyleSheet('background:#0a101a;')
        inner = QWidget()
        inner.setObjectName('NativeScrollBody')
        self.main_pane = vertical(inner, gap=15, margins=(2, 1, 2, 10))
        types = QFrame()
        types.setObjectName("Panel")
        tlay = vertical(types, margins=(16, 15, 16, 16))
        tlay.addWidget(label("Player Types", "Heading"))
        tlay.addWidget(label("Add players, bots, and Psyonix opponents to any team.", "Muted"))
        typebuttons = horizontal(gap=8)
        for caption, kind, skill in [
            ("🎮 Human", "human", ""),
            ("🤖 Rookie", "psyonix", "Rookie"),
            ("🤖 Pro", "psyonix", "Pro"),
            ("🤖 Allstar", "psyonix", "Allstar"),
        ]:
            typebuttons.addWidget(button(caption, lambda _, k=kind, s=skill: self.add_player(k, self.next_team(), s)))
        typebuttons.addWidget(button("＋ Import", self.import_file))
        tlay.addLayout(typebuttons)
        self.main_pane.addWidget(types)
        pres = horizontal()
        pres.addWidget(label("Teams", "Heading"))
        pres.addStretch()
        pres.addWidget(button("1v1 preset", lambda: self.preset(1)))
        pres.addWidget(button("2v2 preset", lambda: self.preset(2)))
        pres.addWidget(button("Reset", self.reset_teams))
        self.main_pane.addLayout(pres)
        teams = horizontal(gap=13)
        self.blue = TeamPanel(self, 0)
        self.orange = TeamPanel(self, 1)
        teams.addWidget(self.blue, 1)
        teams.addWidget(self.orange, 1)
        self.main_pane.addLayout(teams)

        settings = QFrame()
        settings.setObjectName("Panel")
        s = vertical(settings, margins=(16, 15, 16, 17), gap=11)
        s.addWidget(label("Match Settings", "Heading"))
        selectors = horizontal()
        for caption, values, attr in [("Arena", MAPS, "map"), ("Game Mode", MODES, "mode")]:
            block = QWidget()
            column = vertical(block, gap=5)
            column.addWidget(label(caption, "Muted"))
            combo = QComboBox()
            for name, code in values:
                combo.addItem(name, code)
            combo.currentIndexChanged.connect(self.match_setting_changed)
            column.addWidget(combo)
            setattr(self, attr + "_combo", combo)
            selectors.addWidget(block, 1)
        s.addLayout(selectors)
        launcher_row = horizontal()
        launcher_col = vertical(gap=5)
        launcher_col.addWidget(label("Rocket League launcher", "Muted"))
        self.launcher_combo = QComboBox()
        for title, value in LAUNCHERS:
            self.launcher_combo.addItem(title, value)
        self.launcher_combo.currentIndexChanged.connect(self.match_setting_changed)
        launcher_col.addWidget(self.launcher_combo)
        launcher_row.addLayout(launcher_col, 1)
        launcher_row.addWidget(button("Open Heroic / Import RL", self.open_heroic))
        s.addLayout(launcher_row)
        status_line = horizontal()
        self.game_notice = label(explain_game_status(), "Muted", wrap=True)
        status_line.addWidget(self.game_notice, 1)
        status_line.addWidget(button("Check game", self.update_game_readiness))
        s.addLayout(status_line)
        advanced = horizontal()
        advanced.addWidget(button("⚙ Match Mutators", self.edit_mutators))
        advanced.addWidget(button("Extra settings", self.edit_extras))
        advanced.addStretch()
        s.addLayout(advanced)
        s.addWidget(label("All match configurations use RLBotServer V5. V4 bots run via the real legacy API.", "Muted", wrap=True))
        self.main_pane.addWidget(settings)
        self.main_pane.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("Panel")
        control = horizontal(footer, margins=(16, 11, 16, 11))
        control.addWidget(label("Local match", "Heading"))
        self.run_label = label("Ready to launch", "Muted")
        control.addWidget(self.run_label)
        control.addStretch()
        self.start_btn = button("▶  Start Match", self.start_match, "Primary")
        self.start_btn.setMinimumHeight(42)
        control.addWidget(self.start_btn)
        control.addWidget(button("■  Stop", self.stop_match, "Danger"))
        self.main_pane.addWidget(footer)
        return widget

    def _library_page(self):
        pane = QWidget()
        v = vertical(pane, gap=12, margins=(3, 7, 3, 4))
        v.addWidget(label("Imported bots", "Heading"))
        v.addWidget(label("Manage imported RLBot V4 and V5 bots. Source files are never modified.", "Muted"))
        row = horizontal()
        row.addWidget(button("Import bot file…", self.import_file, "Primary"))
        row.addWidget(button("Import folder…", self.import_folder))
        row.addWidget(button("Enter path…", self.import_manual))
        row.addWidget(button("Remove selected from library", self.remove_selected))
        row.addStretch()
        v.addLayout(row)
        self.library_list = QListWidget()
        self.library_list.itemSelectionChanged.connect(self.library_select)
        v.addWidget(self.library_list, 1)
        self.library_info = QPlainTextEdit()
        self.library_info.setReadOnly(True)
        self.library_info.setMaximumHeight(175)
        v.addWidget(self.library_info)
        return pane

    def _logs_page(self):
        pane = QWidget()
        v = vertical(pane, gap=10, margins=(3, 5, 3, 3))
        v.addWidget(label("RLBot engine & bot logs", "Heading"))
        row = horizontal()
        row.addWidget(button("↻ Refresh logs", self.read_logs))
        row.addWidget(button("Open logs folder", self.open_logs_folder))
        row.addStretch()
        v.addLayout(row)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        v.addWidget(self.logs, 1)
        return pane

    def _about_page(self):
        pane = QWidget()
        v = vertical(pane, gap=18, margins=(8, 12, 8, 8))
        v.addWidget(label("Evil RLBot", "Title"))
        for text in [
            "Native Qt Widgets desktop application. This is not a browser or Electron window.",
            "RLBot V5 is the game-facing engine. Native V5 bots run directly; V4 bots run with the original RLBot 1.68 Python frontend using a V5 bridge.",
            f"Project: {ROOT}",
            "CLI legacy match: evil-rlbot-v4cfg /path/to/rlbot.cfg",
            "Run tests: ./evilrlbot-selftest",
            "The match setup supports one local human, additional RLBot agents, and Psyonix AI.",
            "Not all third-party bots can run without their own dependencies. Compatibility with RLBot APIs is not the same as installing every ML runtime.",
        ]:
            v.addWidget(label(text, "Muted", wrap=True))
        v.addStretch()
        return pane

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == index)
        if index == 2:
            self.read_logs()

    def bot_by_id(self, bot_id):
        return next((x for x in self.bots if x.get("id") == bot_id), None)

    def chosen_bot_id(self):
        item = self.bot_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh_bots(self):
        selected = self.chosen_bot_id()
        try:
            self.bots = [backend._bot_payload(x) for x in backend._load_library()]
        except Exception as exc:
            self.error("Could not load bot library", str(exc))
            return
        self.filter_bots()
        self.library_list.clear()
        for b in self.bots:
            obs = b["diagnostics"].get("observation", "unknown")
            desc = f"{'★ ' if b.get('favorite') else ''}{b['name']}    [{b['diagnostics'].get('framework','unknown')}]"
            if obs != "unknown":
                desc += " · " + obs
            item = QListWidgetItem(desc)
            item.setData(Qt.ItemDataRole.UserRole, b["id"])
            self.library_list.addItem(item)
        if selected:
            for i in range(self.bot_list.count()):
                if self.bot_list.item(i).data(Qt.ItemDataRole.UserRole) == selected:
                    self.bot_list.setCurrentRow(i)
                    break
        elif self.bot_list.count():
            self.bot_list.setCurrentRow(0)
        self.redraw()

    def filter_bots(self, *_):
        if not hasattr(self, "bot_list"):
            return
        selected = self.chosen_bot_id()
        query = self.search.text().lower().strip()
        category = self.filter.currentText()
        self.bot_list.clear()
        for b in self.bots:
            if category == "Favorites" and not b.get("favorite"):
                continue
            if category in ("Standard", "ML") and b.get("category") != category:
                continue
            if query not in ("", None) and query not in f"{b['name']} {b['path']} {b['diagnostics']}".lower():
                continue
            profile = b["diagnostics"]
            fw = profile.get("framework", "unknown").replace("rlbot-", "RLBot ").upper()
            obs = profile.get("observation", "unknown")
            text = ("★ " if b.get("favorite") else "") + b["name"] + "\n"
            text += fw
            if obs != "unknown":
                text += " · " + obs
            if not b.get("exists", True):
                text += " · MISSING FILE"
            item = QListWidgetItem(text)
            item.setToolTip(b["path"])
            item.setData(Qt.ItemDataRole.UserRole, b["id"])
            self.bot_list.addItem(item)
        if selected:
            for i in range(self.bot_list.count()):
                if self.bot_list.item(i).data(Qt.ItemDataRole.UserRole) == selected:
                    self.bot_list.setCurrentRow(i)
                    break
        if self.bot_list.currentItem() is None and self.bot_list.count():
            self.bot_list.setCurrentRow(0)

    def on_bot_select(self):
        b = self.bot_by_id(self.chosen_bot_id())
        if not b:
            self.bot_details.setText("Select or import an RLBot bot.")
            return
        p = b["diagnostics"]
        self.bot_details.setText(
            f"Framework: {p.get('framework','unknown')}\n"
            f"Observation: {p.get('observation','unknown')}\n"
            f"Action parser: {p.get('action_parser','unknown')}\n"
            f"Tick skip: {p.get('tick_skip') or 'auto'}"
        )

    def library_select(self):
        item = self.library_list.currentItem()
        if not item:
            return
        b = self.bot_by_id(item.data(Qt.ItemDataRole.UserRole))
        if b:
            self.library_info.setPlainText(json.dumps(b, indent=2))

    def next_team(self):
        blue = sum(p["team"] == 0 for p in self.setup["players"])
        orange = sum(p["team"] == 1 for p in self.setup["players"])
        return 0 if blue <= orange else 1

    def add_player(self, kind, team, value):
        if len(self.setup["players"]) >= 10:
            self.info("Maximum 10 players in this match.")
            return
        if kind == "human" and any(p["kind"] == "human" for p in self.setup["players"]):
            self.info("Only one local human is supported. Add RLBot or Psyonix players for the other slots.")
            return
        p = {"kind": kind, "team": team}
        if kind == "bot":
            if not self.bot_by_id(value):
                self.info("Choose an imported bot in the library first.")
                return
            p["id"] = value
        if kind == "psyonix":
            p["skill"] = value
        self.setup["players"].append(p)
        self.redraw()
        self.schedule_save()

    def add_selected_bot(self, team):
        self.add_player("bot", team, self.chosen_bot_id())

    def remove_player(self, index):
        if len(self.setup["players"]) <= 1:
            self.info("A match must contain at least one player.")
            return
        self.setup["players"].pop(index)
        self.redraw()
        self.schedule_save()

    def duplicate_player(self, index):
        p = dict(self.setup["players"][index])
        self.add_player(p["kind"], p["team"], p.get("id") if p["kind"] == "bot" else p.get("skill", ""))

    def swap_player(self, index):
        player = self.setup["players"][index]
        player["team"] = 1 - player["team"]
        self.redraw()
        self.schedule_save()

    def preset(self, count):
        selected = self.chosen_bot_id()
        second = {"kind": "bot", "id": selected, "team": 1} if selected else {"kind": "psyonix", "team": 1, "skill": "Allstar"}
        lineup = [{"kind": "human", "team": 0}, second]
        if count == 2:
            lineup.extend([{"kind": "bot", "id": selected, "team": 0} if selected else {"kind": "psyonix", "team": 0, "skill": "Pro"},
                          {"kind": "psyonix", "team": 1, "skill": "Allstar"}])
        self.setup["players"] = lineup
        self.redraw()
        self.schedule_save()

    def reset_teams(self):
        self.setup["players"] = [{"kind": "human", "team": 0}]
        self.redraw()
        self.schedule_save()

    def redraw(self):
        self.updating = True
        for combo, field in [(self.map_combo, "map"), (self.mode_combo, "mode"),
                             (self.launcher_combo, "launcher")]:
            i = combo.findData(self.setup.get(field, {"map": "Stadium_P", "mode": "Soccar", "launcher": "Heroic"}[field]))
            if i >= 0:
                combo.setCurrentIndex(i)
        self.updating = False
        self.blue.redraw()
        self.orange.redraw()

    def match_setting_changed(self, *_):
        if self.updating:
            return
        self.setup["map"] = self.map_combo.currentData()
        self.setup["mode"] = self.mode_combo.currentData()
        self.setup["launcher"] = self.launcher_combo.currentData()
        self.schedule_save()

    def edit_mutators(self):
        dlg = MutatorsDialog(self, self.setup)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.setup["mutators"] = dlg.values()
            self.schedule_save()

    def edit_extras(self):
        dlg = OptionsDialog(self, self.setup)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.setup["options"] = dlg.values()
            self.schedule_save()

    def schedule_save(self):
        self.save_timer.start()

    def save_setup(self):
        try:
            normalized = validate_setup(self.setup, backend._bot_paths())
            backend._save_json(backend.SETUP_FILE, normalized)
        except Exception as exc:
            self.run_label.setText("Could not save: " + str(exc))

    def import_file(self):
        name, _ = QFileDialog.getOpenFileName(self, "Import RLBot V4 or V5 bot", str(Path.home()),
                                             "RLBot bot (*.cfg *.toml *.py);;All files (*)")
        if name:
            self.add_path(name)

    def import_folder(self):
        name = QFileDialog.getExistingDirectory(self, "Import RLBot bot folder", str(Path.home()))
        if name:
            self.add_path(name)

    def import_manual(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Import a bot path", "Bot folder, bot.cfg, bot.toml or Python script:")
        if ok and name.strip():
            self.add_path(name.strip())

    def add_path(self, path):
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                raise ValueError(f"File or folder does not exist: {p}")
            from common.detection import detect_bot
            profile = detect_bot(p)
            if profile["framework"] == "unknown":
                raise ValueError("RLBot V4/V5 implementation not detected. Select the bot.cfg, bot.toml or bot folder.")
            library = backend._load_library()
            for item in library:
                if Path(item["path"]).resolve() == p:
                    self.info("That bot is already in the library.")
                    return
            import uuid
            item = {"id": uuid.uuid4().hex, "path": str(p), "favorite": False,
                    "category": "ML" if profile["observation"] != "unknown" else "Standard"}
            library.append(item)
            backend._save_json(backend.LIBRARY_FILE, library)
            self.refresh_bots()
            self.info(f"Imported {p.name}. You can now assign it to Blue or Orange.")
        except Exception as exc:
            self.error("Bot import failed", str(exc))

    def toggle_favorite(self):
        selected = self.chosen_bot_id()
        if not selected:
            return
        lib = backend._load_library()
        item = next((x for x in lib if x.get("id") == selected), None)
        if item:
            item["favorite"] = not item.get("favorite", False)
            backend._save_json(backend.LIBRARY_FILE, lib)
            self.refresh_bots()

    def selected_diagnostics(self):
        b = self.bot_by_id(self.chosen_bot_id())
        if not b:
            self.info("Select a bot first.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Bot Diagnostics — " + b["name"])
        dialog.resize(780, 540)
        v = vertical(dialog, margins=(13, 13, 13, 13))
        v.addWidget(label(b["name"], "Heading"))
        v.addWidget(label(b["path"], "Muted", wrap=True))
        text = QPlainTextEdit(json.dumps(b["diagnostics"], indent=2))
        text.setReadOnly(True)
        v.addWidget(text)
        v.addWidget(button("Close", dialog.accept))
        dialog.exec()

    def remove_selected(self):
        item = self.library_list.currentItem()
        if not item:
            return
        bot_id = item.data(Qt.ItemDataRole.UserRole)
        b = self.bot_by_id(bot_id)
        if QMessageBox.question(self, "Remove bot", f"Remove {b['name']} from the library?\nBot source files will not be deleted.") != QMessageBox.StandardButton.Yes:
            return
        lib = [x for x in backend._load_library() if x["id"] != bot_id]
        backend._save_json(backend.LIBRARY_FILE, lib)
        self.setup["players"] = [p for p in self.setup["players"] if p.get("id") != bot_id]
        if not self.setup["players"]:
            self.setup["players"] = [{"kind": "human", "team": 0}]
        self.refresh_bots()
        self.redraw()
        self.schedule_save()

    def run_worker(self, action, finished_label):
        if self.busy:
            return
        self.busy = True
        self.start_btn.setEnabled(False)
        self.run_label.setText(finished_label)
        self.worker = Worker(action, self)
        self.worker.success.connect(self.operation_success)
        self.worker.failed.connect(self.operation_failed)
        self.worker.finished.connect(self.operation_end)
        self.worker.start()

    def update_game_readiness(self):
        self.game_notice.setText(explain_game_status())

    def start_match(self):
        info = inspect_game()
        if info["eos_launcher_error"] and self.setup.get("launcher") == "Heroic":
            self.update_game_readiness()
            choice = QMessageBox.question(
                self, "Epic launcher initialization required",
                "Rocket League files are present, but the last standalone launch failed before the menu "
                "because Epic Online Services could not initialize. Offline bot matches do not "
                "require matchmaking, but the game still needs an authenticated Heroic/Epic "
                "launcher session. Open Heroic, sign in once, and import the existing game files. "
                "Do you want to attempt to start the match anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        try:
            setup = validate_setup(self.setup, backend._bot_paths())
            self.save_setup()
        except Exception as exc:
            self.error("Invalid match", str(exc))
            return
        self.run_worker(lambda: ("start", backend._start_match(setup)), "Starting native RLBot V5…")

    def stop_match(self):
        self.run_worker(lambda: ("stop", backend._stop_match()), "Stopping match…")

    def operation_success(self, result):
        action, value = result
        if action == "start":
            self.run_label.setText("Match started · PID " + str(value["pid"]))
        else:
            self.run_label.setText("Match stopped")
        self.update_status()

    def operation_failed(self, message):
        self.run_label.setText("Operation failed")
        self.error("RLBot engine error", message)
        self.update_status()

    def operation_end(self):
        self.busy = False
        self.start_btn.setEnabled(True)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def update_status(self):
        if self.busy:
            return
        state = backend._status()
        if state["running"]:
            self.global_status.setText("● V5 RUNNING")
            self.global_status.setStyleSheet("color:#67f1a5;font-weight:800")
            self.run_label.setText("Match live · PID " + str(state["pid"]))
        elif state.get("exit_code") not in (None, 0):
            self.global_status.setText("● ENGINE STOPPED")
            self.global_status.setStyleSheet("color:#ffad80;font-weight:700")
            self.run_label.setText("Exited with code " + str(state["exit_code"]) + " — see Logs")
        else:
            self.global_status.setText("● READY")
            self.global_status.setStyleSheet("color:#a4b5ca")
            self.run_label.setText("Ready to launch")

    def read_logs(self):
        try:
            text = backend.LOG.read_text(errors="replace")[-150_000:] if backend.LOG.exists() else "No match logs yet."
            self.logs.setPlainText(text)
            sb = self.logs.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception as exc:
            self.logs.setPlainText(str(exc))

    def open_heroic(self):
        import shutil
        import subprocess
        if shutil.which("flatpak") is None:
            self.error("Heroic not available", "Flatpak is not installed on this system.")
            return
        if subprocess.run(["flatpak", "info", "com.heroicgameslauncher.hgl"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            self.info("Heroic is not yet installed. Open the application store and install Heroic Games Launcher.")
            return
        try:
            env = os.environ.copy()
            env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
            # Hyprland starts Qt on Wayland; Heroic Electron may require XWayland.
            if not env.get("DISPLAY") and Path("/tmp/.X11-unix/X0").exists():
                env["DISPLAY"] = ":0"
            subprocess.Popen(["flatpak", "run", "com.heroicgameslauncher.hgl"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, env=env)
            self.info("Heroic is starting. Sign in to Epic once, then use Heroic’s Import Game feature to select ~/Games/RocketLeagueOffline. No need to redownload 40 GB. Afterwards, return here and select Heroic (Epic Games).")
        except Exception as exc:
            self.error("Unable to open Heroic", str(exc))

    def open_logs_folder(self):
        target = ROOT / "logs"
        target.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def info(self, message):
        QMessageBox.information(self, "Evil RLBot", message)

    def error(self, title, message):
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event):
        # Preserve an active bot match if only the GUI is closed? The backend
        # subprocess starts a new process session; by default keep it running.
        self.save_timer.stop()
        self.save_setup()
        if self.worker and self.worker.isRunning():
            self.worker.wait(5000)
        event.accept()


def main():
    os.environ.setdefault("QT_QPA_PLATFORMTHEME", "gtk3")
    app = QApplication(sys.argv)
    app.setApplicationName("Evil RLBot")
    app.setDesktopFileName("evil-rlbot")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    app.setWindowIcon(logo_icon())
    win = NativeWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
