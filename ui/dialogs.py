"""Evil RLBot dialog components: sheets, toasts, progress and settings dialogs.

Every popup in the classic window is built from `Sheet` so they share one look:
the main window dims, a rounded panel fades in with a header (optional logo,
title, subtitle, close button), a body and a footer row of buttons.
"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QPropertyAnimation, QTimer, Qt,
                            Signal)
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame,
                               QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
                               QTabBar, QVBoxLayout, QWidget)

ACCENTS = {"info": "#5b9bd5", "success": "#4caf61", "warning": "#e0a43a",
           "error": "#e05252", "blue": "#0d5bb0", "orange": "#ea6b1e"}

DIALOG_CSS = """
QFrame#Sheet {background:#16191c; border:1px solid #2c3035; border-radius:8px}
QFrame#SheetFooter {background:#121417; border-top:1px solid #2a2e33; border-bottom-left-radius:8px; border-bottom-right-radius:8px}
QLabel#SheetTitle {color:#fff; font:700 16px 'Segoe UI','Noto Sans',Arial}
QLabel#SheetSub {color:#8b9196; font-size:12px}
QLabel#Body {color:#c9cdd1; font-size:13px}
QLabel#Key {color:#7d8388; font-size:12px}
QLabel#Value {color:#e4e6e8; font-size:12px}
QLabel#Section {color:#7d8388; font:600 11px 'Segoe UI','Noto Sans',Arial; letter-spacing:0.5px}
QLabel#Tag {background:#24282c; color:#c5c9cc; border-radius:3px; padding:2px 7px; font-size:11px}
QLabel#Ok {color:#6fcf7f; font-size:12px}
QLabel#Warn {color:#e0b04a; font-size:12px}
QLabel#Bad {color:#ff7070; font-size:12px}
QFrame#Rule {background:#2a2e33; max-height:1px; min-height:1px}
QFrame#Row {background:#1b1e22; border-radius:5px}
QFrame#Row:hover {background:#20242a}
QPushButton#Close {background:transparent; color:#7d8388; font-size:16px; padding:0 4px; min-width:22px; min-height:22px}
QPushButton#Close:hover {color:#fff; background:#24282c}
QPushButton#Primary {background:#e4e6e8; color:#15181b; font-weight:600}
QPushButton#Primary:hover {background:#ffffff}
QPushButton#Danger {background:#b42323; color:#fff; font-weight:600}
QPushButton#Danger:hover {background:#c92b2b}
QPushButton#BlueBtn {background:#0d5bb0; color:#fff; font-weight:600}
QPushButton#BlueBtn:hover {background:#1468c2}
QPushButton#OrangeBtn {background:#ea6b1e; color:#fff; font-weight:600}
QPushButton#OrangeBtn:hover {background:#f27a30}
QPushButton#Link {background:transparent; color:#8fb4d9; padding:2px 4px}
QPushButton#Link:hover {color:#b9d3ee}
QPushButton#Seg {background:transparent; border:1px solid #3a3f44; border-radius:0; padding:5px 16px}
QPushButton#Seg:checked {background:#e4e6e8; color:#15181b; border-color:#e4e6e8}
QFrame#Toast {background:#1d2024; border:1px solid #30353b; border-radius:6px}
QLabel#ToastText {color:#e4e6e8; font-size:12px}
QCheckBox {spacing:9px; color:#e4e6e8}
QCheckBox::indicator {width:16px; height:16px; border-radius:3px; border:1px solid #4a5056; background:#1b1e22}
QCheckBox::indicator:checked {background:#e4e6e8; border-color:#e4e6e8}
QProgressBar {background:#24282c; border:none; border-radius:2px; max-height:4px; min-height:4px}
QProgressBar::chunk {background:#5b9bd5; border-radius:2px}
QTabBar::tab {background:transparent; color:#8b9196; padding:7px 12px; border-bottom:2px solid transparent}
QTabBar::tab:selected {color:#fff; border-bottom-color:#e4e6e8}
QTabBar::tab:hover {color:#fff}
"""


def rule():
    line = QFrame()
    line.setObjectName("Rule")
    return line


def text_label(text, role="Body", wrap=True):
    label = QLabel(text)
    label.setObjectName(role)
    label.setWordWrap(wrap)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class _Dim(QWidget):
    """Translucent layer over the main window while a sheet is open."""

    def __init__(self, window):
        super().__init__(window)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(window.rect())
        self.show()
        self.raise_()

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect(), QColor(0, 0, 0, 120))


class Sheet(QDialog):
    def __init__(self, parent, title, subtitle="", *, logo=None, width=460, accent=None):
        super().__init__(parent)
        self.choice = None
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("Sheet")
        outer.addWidget(frame)
        column = QVBoxLayout(frame)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self.header = QWidget()
        head = QHBoxLayout(self.header)
        head.setContentsMargins(18, 16, 12, 12)
        head.setSpacing(13)
        if logo is not None:
            image = QLabel()
            image.setPixmap(logo)
            image.setFixedSize(logo.size())
            head.addWidget(image, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        name = QLabel(title)
        name.setObjectName("SheetTitle")
        if accent:
            name.setText(f'<span style="color:{ACCENTS.get(accent, accent)}">●</span>&nbsp; {title}')
        titles.addWidget(name)
        self.tags = QHBoxLayout()
        self.tags.setSpacing(5)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("SheetSub")
            sub.setWordWrap(True)
            sub.setMinimumWidth(min(width - 150, sub.fontMetrics().horizontalAdvance(subtitle) + 4))
            titles.addWidget(sub)
        titles.addLayout(self.tags)
        head.addLayout(titles)
        head.addStretch(1)
        close = QPushButton("✕")
        close.setObjectName("Close")
        close.setFixedSize(26, 26)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.reject)
        head.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        column.addWidget(self.header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(18, 2, 18, 18)
        self.body.setSpacing(10)
        column.addLayout(self.body, 1)

        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("SheetFooter")
        self.footer = QHBoxLayout(self.footer_frame)
        self.footer.setContentsMargins(14, 12, 14, 12)
        self.footer.setSpacing(6)
        self.footer_frame.hide()
        column.addWidget(self.footer_frame)
        self._drag = None
        self._dim = None

    def add_tag(self, text):
        tag = QLabel(text)
        tag.setObjectName("Tag")
        self.tags.addWidget(tag)
        return tag

    def add_button(self, text, role="", *, result=None, callback=None, left=False):
        """Footer button. `result` closes the sheet with that choice."""
        self.footer_frame.show()
        button = QPushButton(text)
        if role:
            button.setObjectName(role)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if callback:
            button.clicked.connect(callback)
        if result is not None:
            button.clicked.connect(lambda: self.finish(result))
        if left:
            self.footer.insertWidget(self._left_count(), button)
        else:
            if not any(self.footer.itemAt(i).spacerItem() for i in range(self.footer.count())):
                self.footer.addStretch()
            self.footer.addWidget(button)
        if role == "Primary":
            button.setDefault(True)
        return button

    def _left_count(self):
        for i in range(self.footer.count()):
            if self.footer.itemAt(i).spacerItem():
                return i
        self.footer.addStretch()
        return self.footer.count() - 1

    def finish(self, result):
        self.choice = result
        self.accept()

    # Drag the sheet by its header, like a title bar.
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.header.geometry().contains(event.pos()):
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event):
        self._drag = None

    def showEvent(self, event):
        super().showEvent(event)
        window = self.parentWidget().window() if self.parentWidget() else None
        if window is not None and self._dim is None and not isinstance(window, Sheet):
            self._dim = _Dim(window)
        self.adjustSize()
        self.layout().invalidate()
        self.layout().activate()
        if window is not None:
            center = window.geometry().center()
            self.move(center - QPoint(self.width() // 2, self.height() // 2))
        self.setWindowOpacity(0)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(140)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start()

    def done(self, result):
        if self._dim is not None:
            self._dim.hide()
            self._dim.deleteLater()
            self._dim = None
        super().done(result)


def message(parent, title, text, *, kind="info", details=None, buttons=None):
    """A message sheet. Returns the chosen button's result (None if closed)."""
    sheet = Sheet(parent, title, accent=kind, width=440)
    sheet.body.addWidget(text_label(text))
    if details:
        box = QPlainTextEdit(details)
        box.setReadOnly(True)
        box.setMinimumHeight(170)
        box.hide()
        toggle = QPushButton("Show details")
        toggle.setObjectName("Link")
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)

        def flip():
            box.setVisible(not box.isVisible())
            toggle.setText("Hide details" if box.isVisible() else "Show details")
            sheet.setMinimumWidth(620 if box.isVisible() else 440)
            sheet.adjustSize()
        toggle.clicked.connect(flip)
        sheet.body.addWidget(toggle, 0, Qt.AlignmentFlag.AlignLeft)
        sheet.body.addWidget(box)
        copy = sheet.add_button("Copy details", left=True)
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(details), copy.setText("Copied")))
    for label, result, role in buttons or [("OK", True, "Primary")]:
        sheet.add_button(label, role, result=result)
    sheet.exec()
    return sheet.choice


def confirm(parent, title, text, action, *, danger=False):
    return message(parent, title, text, kind="warning" if danger else "info",
                   buttons=[("Cancel", False, ""), (action, True, "Danger" if danger else "Primary")]) is True


class ProgressSheet(Sheet):
    """Non-blocking progress for long jobs such as package installs."""
    canceled = Signal()

    def __init__(self, parent, title, text):
        super().__init__(parent, title, width=520)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._canceled = False
        self.line = text_label(text)
        self.body.addWidget(self.line)
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        self.body.addWidget(bar)
        self.add_button("Cancel", callback=self._cancel)

    def _cancel(self):
        if not self._canceled:
            self._canceled = True
            self.line.setText("Cancelling…")
            self.canceled.emit()

    def reject(self):
        self._cancel()

    def wasCanceled(self):
        return self._canceled

    def setLabelText(self, text):
        self.line.setText(text)

    def close(self):
        self.done(0)
        return True


class Spinner(QWidget):
    """Small rotating arc shown while something loads; hidden when idle."""

    def __init__(self, size=16, color="#c5c9cc"):
        super().__init__()
        self.setFixedSize(size, size)
        self.color = QColor(color)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.hide()

    @property
    def active(self):
        return self.timer.isActive()

    def start(self):
        self.show()
        self.timer.start(16)

    def stop(self):
        self.timer.stop()
        self.hide()

    def _tick(self):
        self.angle = (self.angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = painter.pen()
        pen.setWidthF(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setColor(self.color)
        painter.setPen(pen)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.drawArc(rect, -self.angle * 16, 270 * 16)


class Toast(QFrame):
    """Short notice at the bottom of the window that fades out by itself."""
    _current = None

    def __init__(self, window, text, kind="info", action=None, timeout=3600):
        super().__init__(window)
        self.setObjectName("Toast")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 9, 10, 9)
        row.setSpacing(10)
        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f"background:{ACCENTS.get(kind, kind)}; border-radius:1px")
        row.addWidget(bar)
        label = QLabel(text)
        label.setObjectName("ToastText")
        row.addWidget(label)
        if action:
            title, callback = action
            link = QPushButton(title)
            link.setObjectName("Link")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.clicked.connect(lambda: (callback(), self.dismiss()))
            row.addWidget(link)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.adjustSize()
        self.place()
        window.installEventFilter(self)
        self.show()
        self.raise_()
        self._fade(0, 1, 150)
        QTimer.singleShot(timeout, self.dismiss)

    def place(self):
        window = self.parentWidget()
        self.move((window.width() - self.width()) // 2, window.height() - self.height() - 112)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.place()
        return False

    def _fade(self, start, end, ms, done=None):
        anim = QPropertyAnimation(self.effect, b"opacity", self)
        anim.setDuration(ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        if done:
            anim.finished.connect(done)
        anim.start()

    def dismiss(self):
        if self.isVisible() and self.effect.opacity() > 0.99:
            self._fade(1, 0, 220, self.deleteLater)

    @classmethod
    def show_message(cls, window, text, kind="info", action=None, timeout=3600):
        if cls._current is not None:
            try:
                cls._current.deleteLater()
            except RuntimeError:
                pass
        cls._current = cls(window, text, kind, action, timeout)
        return cls._current


class MutatorsSheet(Sheet):
    def __init__(self, parent, setup):
        from ui.native import DEFAULT_MUTATORS, MUTATOR_LABELS, MUTATOR_TITLES, MUTATORS
        super().__init__(parent, "Mutators", "Change how the match plays.", width=640)
        self.defaults = DEFAULT_MUTATORS
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(420)
        content = QWidget()
        content.setObjectName("BotContent")
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 8, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        self.controls = {}
        current = setup.get("mutators", {})
        for index, key in enumerate(MUTATOR_TITLES):
            cell = QVBoxLayout()
            cell.setSpacing(4)
            cell.addWidget(text_label(MUTATOR_TITLES[key], "Key", False))
            combo = QComboBox()
            for value in sorted(MUTATORS[key], key=lambda x: (x != "Default", x != "Unlimited", x)):
                combo.addItem(MUTATOR_LABELS.get(value, value), value)
            combo.setCurrentIndex(max(0, combo.findData(current.get(key, DEFAULT_MUTATORS[key]))))
            cell.addWidget(combo)
            grid.addLayout(cell, index // 2, index % 2)
            self.controls[key] = combo
        scroll.setWidget(content)
        self.body.addWidget(scroll)
        self.add_button("Reset to defaults", left=True, callback=self.reset)
        self.add_button("Cancel", result=False)
        self.add_button("Save", "Primary", result=True)

    def reset(self):
        for key, combo in self.controls.items():
            combo.setCurrentIndex(combo.findData(self.defaults[key]))

    def values(self):
        return {key: combo.currentData() for key, combo in self.controls.items()}


class ExtraSheet(Sheet):
    def __init__(self, parent, setup):
        from ui.native import DEFAULT_OPTIONS, OPTION_TITLES
        super().__init__(parent, "Extra settings", "Options passed to Rocket League for this match.")
        self.checks = {}
        for key, title in OPTION_TITLES.items():
            box = QCheckBox(title)
            box.setChecked(bool(setup.get("options", {}).get(key, DEFAULT_OPTIONS[key])))
            self.body.addWidget(box)
            self.checks[key] = box
        self.add_button("Cancel", result=False)
        self.add_button("Save", "Primary", result=True)

    def values(self):
        return {key: box.isChecked() for key, box in self.checks.items()}


class LogsSheet(Sheet):
    def __init__(self, parent, logs, open_folder=None):
        super().__init__(parent, "Logs", "Match, bot worker and package install logs.", width=900)
        self.logs = logs
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMinimumHeight(460)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        if logs:
            for name in logs:
                self.tabs.addTab(name.split("/")[-1])
            self.tabs.currentChanged.connect(self.select)
            self.body.addWidget(self.tabs)
            self.select(0)
        else:
            self.view.setPlainText("No logs yet. They appear here after a match or a package install.")
        self.body.addWidget(self.view, 1)
        copy = self.add_button("Copy", left=True)
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(self.view.toPlainText()),
                                      copy.setText("Copied")))
        if open_folder:
            self.add_button("Open logs folder", left=True, callback=open_folder)
        self.add_button("Close", "Primary", result=True)

    def select(self, index):
        names = list(self.logs)
        if 0 <= index < len(names):
            self.view.setPlainText(self.logs[names[index]])
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
