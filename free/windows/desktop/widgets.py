"""Anchor's building blocks in Qt: icons, spinner, switch, toasts, dialogs, cards and rows."""

import hashlib
from pathlib import Path

from PySide6.QtCore import (QByteArray, QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation, QRectF,
                            QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

import theme

HERE = Path(__file__).resolve().parent
ICONS = HERE / "icons"

# Material Design icon paths (Apache 2.0), drawn in any colour.
PATHS = {
    "search": "M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 "
              "4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 "
              "7.01 14 9.5 11.99 14 9.5 14z",
    "menu": "M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z",
    "expand-more": "M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z",
    "expand-less": "M12 8l-6 6 1.41 1.41L12 10.83l4.59 4.58L18 14z",
    "chevron-right": "M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z",
    "add": "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
    "delete": "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z",
    "close": "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 "
             "17.59 13.41 12z",
    "alarm": "M22 5.72l-4.6-3.86-1.29 1.53 4.6 3.86L22 5.72zM7.88 3.39L6.6 1.86 2 5.71l1.29 1.53 "
             "4.59-3.85zM12.5 8H11v6l4.75 2.85.75-1.23-4-2.37V8zM12 4c-4.97 0-9 4.03-9 9s4.02 9 9 9c4.97 "
             "0 9-4.03 9-9s-4.03-9-9-9zm0 16c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z",
    # Never allow: copied from the phone app (android/res/drawable/ic_block.xml), so both look the same.
    "block": "M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2zM4,12c0,-4.42 3.58,-8 8,-8 1"
             ".85,0 3.55,0.63 4.9,1.69L5.69,16.9C4.63,15.55 4,13.85 4,12zM12,20c-1.85,0 -3.55,-0.63 -4.9,-1.69L18.31,7.1C19.37,8.45 20,10.15 20,12c0,4.42 -3.58,8 -8,8z",
    "grid": "M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm"
            "-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z",
    "anchor": "M12,2A3,3 0 0,0 9,5C9,6.27 9.8,7.4 11,7.83V10H8V12H11V18.92C9.16,18.63 7.53,17.57 6.53,16"
              "H8V14H3V19H5V17.3C6.58,19.61 9.2,21 12,21C14.8,21 17.42,19.61 19,17.3V19H21V14H16V16H17.46"
              "C16.46,17.56 14.83,18.63 13,18.92V12H16V10H13V7.82C14.2,7.4 15,6.27 15,5A3,3 0 0,0 12,2M12,4"
              "A1,1 0 0,1 13,5A1,1 0 0,1 12,6A1,1 0 0,1 11,5A1,1 0 0,1 12,4Z",
    "phone": "M16 1H8C6.34 1 5 2.34 5 4v16c0 1.66 1.34 3 3 3h8c1.66 0 3-1.34 3-3V4c0-1.66-1.34-3-3-3zm-2 "
             "20h-4v-1h4v1zm3.25-3H6.75V4h10.5v14z",
    "warning": "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
    "lock": "M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 "
            "2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 "
            "1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z",
    "key": "M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0 4.83-1.67 5.65-4H17v4h4v-4"
           "h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z",
    "check": "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
    "info": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7"
            "h2v2z",
    "group": "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 "
             "2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5"
             "c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33"
             "-4.67-3.5-7-3.5z",
    "person": "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2"
              "c0-2.66-5.33-4-8-4z",
    "usb-allow": "M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41"
                 "L10 14.17l6.59-6.59L18 9l-8 8z",
}

_cache = {}


def svg_pixmap(svg_bytes, size, dpr=2.0):
    key = (svg_bytes, size, dpr)
    if key not in _cache:
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        w, h = (size, size) if isinstance(size, int) else size
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        renderer.render(p)
        p.end()
        pm.setDevicePixelRatio(dpr)
        _cache[key] = pm
    return _cache[key]


def svg_fill(color):
    """An SVG fill for "#RRGGBB" or CSS "rgba(r, g, b, a)": Qt's SVG renderer doesn't read rgba()."""
    if color.startswith("rgba("):
        r, g, b, a = (x.strip() for x in color[5:-1].split(","))
        return f'fill="#{int(r):02X}{int(g):02X}{int(b):02X}" fill-opacity="{float(a)}"'
    return f'fill="{color}"'


def symbol(name, color=theme.TEXT, size=20):
    """One of PATHS as a pixmap in `color`."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           f'<path {svg_fill(color)} d="{PATHS[name]}"/></svg>').encode()
    return svg_pixmap(svg, size)


def symbol_icon(name, color=theme.TEXT, size=20):
    icon = QIcon(symbol(name, color, size))
    icon.addPixmap(symbol(name, "rgba(238, 234, 247, 0.3)", size), QIcon.Disabled)
    return icon


def picture(filename, size):
    """One of the SVGs in icons/ (the orbs, the app icon) as a pixmap."""
    return svg_pixmap((ICONS / filename).read_bytes(), size)


def rounded(pixmap, size, radius):
    dpr = 2.0
    out = QPixmap(int(size * dpr), int(size * dpr))
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size * dpr, size * dpr), radius * dpr, radius * dpr)
    p.setClipPath(path)
    p.drawPixmap(out.rect(), pixmap)
    p.end()
    out.setDevicePixelRatio(dpr)
    return out


def app_pixmap(png, label, size=40):
    """The app's own icon when the phone sent one, else a round avatar with its initial."""
    if png:
        pm = QPixmap()
        if pm.loadFromData(png):
            return rounded(pm, size, size * 0.3)
    hue = int(hashlib.md5(label.encode()).hexdigest()[:4], 16) % 360
    dpr = 2.0
    out = QPixmap(int(size * dpr), int(size * dpr))
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, size * dpr, size * dpr)
    grad.setColorAt(0, QColor.fromHsl(hue, 150, 120))
    grad.setColorAt(1, QColor.fromHsl((hue + 30) % 360, 160, 80))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(0, 0, size * dpr, size * dpr))
    font = p.font()
    font.setPixelSize(int(size * dpr * 0.42))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, 0, size * dpr, size * dpr), Qt.AlignCenter, (label[:1] or "?").upper())
    p.end()
    out.setDevicePixelRatio(dpr)
    return out


def set_kind(button, kind):
    """Switches a button's look (the `kind` style property) and repaints it."""
    if button.property("kind") != kind:
        button.setProperty("kind", kind)
        button.style().unpolish(button)
        button.style().polish(button)


def set_flag(widget, name, value):
    if widget.property(name) != value:
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def shadow(widget, blur=36, alpha=110, dy=8):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


def button(text, kind, tooltip=None, on_click=None):
    b = QPushButton(text)
    b.setProperty("kind", kind)
    b.setCursor(Qt.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    if on_click:
        b.clicked.connect(lambda *_: on_click())
    return b


def icon_button(name, tooltip, on_click=None, color=theme.TEXT, size=20, kind="icon"):
    b = QPushButton()
    b.setProperty("kind", kind)
    b.setIcon(symbol_icon(name, color, size))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tooltip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedSize(size + 16, size + 16)
    if on_click:
        b.clicked.connect(lambda *_: on_click())
    return b


def label(text="", name=None, wrap=False, align=None, rich=False, selectable=False):
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    lbl.setTextFormat(Qt.RichText if rich else Qt.PlainText)
    if rich:
        lbl.setOpenExternalLinks(True)
    if align is not None:
        lbl.setAlignment(align)
    if selectable:
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lbl


def image(pixmap):
    lbl = QLabel()
    lbl.setPixmap(pixmap)
    lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
    return lbl


class ElidedLabel(QLabel):
    """A one-line label that ends in … when it doesn't fit (QLabel itself never elides)."""

    def __init__(self, text="", name=None):
        super().__init__(text)
        if name:
            self.setObjectName(name)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(10)

    def paintEvent(self, _event):
        p = QPainter(self)
        rect = self.contentsRect()
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        p.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter,
                   self.fontMetrics().elidedText(self.text(), Qt.ElideRight, rect.width()))


class Spinner(QWidget):
    """A violet arc that turns while something is happening."""

    def __init__(self, size=24, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def showEvent(self, _e):
        self.timer.start(16)

    def hideEvent(self, _e):
        self.timer.stop()

    def _tick(self):
        self.angle = (self.angle + 6) % 360
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = max(2.0, self.width() / 9)
        rect = QRectF(w, w, self.width() - 2 * w, self.height() - 2 * w)
        p.setPen(QPen(QColor(255, 255, 255, 25), w))
        p.drawEllipse(rect)
        pen = QPen(QColor(theme.ACCENT), w)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, -self.angle * 16, 100 * 16)


class Switch(QAbstractButton):
    """An on/off switch like libadwaita's: violet when on, the knob slides."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._pos = 1.0 if checked else 0.0
        self.anim = QVariantAnimation(self, duration=140, easingCurve=QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._moved)
        self.toggled.connect(self._animate)

    def _moved(self, v):
        self._pos = v
        self.update()

    def _animate(self, on):
        self.anim.stop()
        self.anim.setStartValue(self._pos)
        self.anim.setEndValue(1.0 if on else 0.0)
        self.anim.start()

    def set_quietly(self, on):
        """Sets the state without telling anyone (no toggled signal)."""
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        self.anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off, on = QColor(255, 255, 255, 31), QColor(theme.VIOLET)
        mix = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
            int(off.alpha() + (on.alpha() - off.alpha()) * self._pos))
        p.setPen(Qt.NoPen)
        p.setBrush(mix)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        p.setBrush(QColor("#F4F0FF"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))

    def sizeHint(self):
        return QSize(46, 26)


class Toasts(QWidget):
    """Short messages in a pill at the bottom of the window, one at a time."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.pill = QLabel(self)
        self.pill.setObjectName("toast")
        self.pill.setWordWrap(True)
        self.pill.setAlignment(Qt.AlignCenter)  # no shadow: it would sit inside the fade effect
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b"opacity", self, duration=180)
        self.hide_timer = QTimer(self, singleShot=True)
        self.hide_timer.timeout.connect(self._fade_out)
        self.hide()
        parent.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self._place()
        return False

    def show_text(self, text, timeout=3):
        self.pill.setText(text)
        self._place()
        self.show()
        self.raise_()
        self.fade.stop()
        self.fade.setStartValue(self.opacity.opacity() if self.isVisible() else 0.0)
        self.fade.setEndValue(1.0)
        self.fade.start()
        self.hide_timer.start(int(timeout * 1000))

    def _fade_out(self):
        self.fade.stop()
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.start()
        QTimer.singleShot(200, lambda: self.opacity.opacity() < 0.05 and self.hide())

    def _place(self):
        parent = self.parentWidget()
        width = min(520, parent.width() - 48)
        self.pill.setFixedWidth(width)
        self.pill.adjustSize()
        h = self.pill.height() + 40
        self.setGeometry(0, parent.height() - h - 8, parent.width(), h)
        self.pill.move((parent.width() - width) // 2, 10)


# ---- Dialogs ------------------------------------------------------------------------------------

class Overlay(QWidget):
    """A dimmed layer over the window holding a centred panel: Anchor's dialogs live inside the
    window, like libadwaita's, so they look the same on every system."""

    closed = Signal()

    def __init__(self, window, width=420, max_height=None):
        super().__init__(window.centralWidget())
        self.window_ = window
        self.panel = QFrame(self)
        self.panel.setObjectName("dialog")
        self.panel_width, self.max_height = width, max_height
        shadow(self.panel, 60, 160, 16)
        self.setFocusPolicy(Qt.StrongFocus)
        self.hide()
        self.parentWidget().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize and self.isVisible():
            self._place()
        return False

    def paintEvent(self, _e):
        QPainter(self).fillRect(self.rect(), QColor(5, 3, 10, 150))

    def _place(self):
        parent = self.parentWidget()
        self.setGeometry(parent.rect())
        width = min(self.panel_width, parent.width() - 32)
        self.panel.setFixedWidth(width)
        limit = parent.height() - 48
        if self.max_height:
            h = min(limit, self.max_height)
        else:
            # Wrapped text is taller at a narrow width: ask the layout for its height at this width
            # (sizeHint() measures it unwrapped, which cut off the end of long messages).
            lay = self.panel.layout()
            h = lay.totalHeightForWidth(width) if lay and lay.hasHeightForWidth() else self.panel.sizeHint().height()
            h = min(h, limit)
        self.panel.setFixedHeight(max(h, 0))
        self.panel.move((parent.width() - width) // 2, max(16, (parent.height() - self.panel.height()) // 2))

    def present(self, _parent=None):
        self._place()
        self.show()
        self.raise_()
        self.setFocus()
        QTimer.singleShot(0, self._place)

    def mousePressEvent(self, ev):
        if not self.panel.geometry().contains(ev.position().toPoint()):
            self.dismiss()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(ev)

    def dismiss(self):
        self.close_overlay()

    def close_overlay(self):
        if self.isVisible() or self.parent():
            self.hide()
            self.closed.emit()
            self.deleteLater()


class AlertDialog(Overlay):
    """Heading, body, an optional extra widget and a row of buttons. Like Adw.AlertDialog:
    add_response(id, label), set_response_appearance(id, "suggested"|"destructive"), and the
    `response` signal with the id of the button pressed."""

    response = Signal(str)

    def __init__(self, window, heading, body=None, width=420):
        super().__init__(window, width)
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(26, 26, 26, 22)
        lay.setSpacing(12)
        self.heading = label(heading, "dialogHeading", wrap=True, align=Qt.AlignCenter)
        lay.addWidget(self.heading)
        self.body = label(body or "", "dialogBody", wrap=True, align=Qt.AlignCenter)
        self.body.setVisible(bool(body))
        lay.addWidget(self.body)
        self.extra_slot = QVBoxLayout()
        self.extra_slot.setContentsMargins(0, 6, 0, 0)
        lay.addLayout(self.extra_slot)
        self.extra = None
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(10)
        self.buttons.setContentsMargins(0, 10, 0, 0)
        lay.addLayout(self.buttons)
        self.responses = {}
        self.default_response = None
        self.close_response = None

    # libadwaita-style API, so the window code reads the same on both apps.
    def get_heading(self):
        return self.heading.text()

    def get_body(self):
        return self.body.text()

    def set_body(self, text):
        self.body.setText(text)
        self.body.setVisible(bool(text))

    def set_extra_child(self, widget):
        self.extra = widget
        self.extra_slot.addWidget(widget)

    def get_extra_child(self):
        return self.extra

    def add_response(self, rid, text):
        b = button(text, "dialog", on_click=lambda: self.emit_response(rid))
        b.setMinimumHeight(40)
        self.buttons.addWidget(b, 1)
        self.responses[rid] = b
        if self.close_response is None:
            self.close_response = rid

    def set_response_appearance(self, rid, appearance):
        set_kind(self.responses[rid], f"dialog-{appearance}")

    def set_default_response(self, rid):
        self.default_response = rid

    def set_close_response(self, rid):
        self.close_response = rid

    def emit_response(self, rid):
        self.close_overlay()
        self.response.emit(rid)

    def connect(self, signal, handler):  # noqa: A003 - mirrors GObject's d.connect("response", ...)
        assert signal == "response"
        self.response.connect(lambda rid: handler(self, rid))

    def emit(self, signal, rid):  # noqa: A003 - lets tests press a button like with GTK
        assert signal == "response"
        self.emit_response(rid)

    def dismiss(self):
        self.emit_response(self.close_response or "close")

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and self.default_response:
            self.emit_response(self.default_response)
        else:
            super().keyPressEvent(ev)


class PanelDialog(Overlay):
    """A taller dialog with a title bar, a close button and scrolling content (app details, About)."""

    def __init__(self, window, title="", width=460, height=640):
        super().__init__(window, width, max_height=height)
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(18, 14, 14, 4)
        self.title = label(title, "title", align=Qt.AlignCenter)
        bar.addSpacing(32)
        bar.addWidget(self.title, 1)
        bar.addWidget(icon_button("close", "Close", self.close_overlay, size=18))
        lay.addLayout(bar)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("panelContent")
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(20, 6, 20, 22)
        self.body.setSpacing(18)
        scroller.setWidget(self.content)
        lay.addWidget(scroller, 1)

    def get_title(self):
        return self.title.text()


# ---- Cards, groups and rows -------------------------------------------------------------------

class Row(QFrame):
    """A list row: an optional picture, a title and subtitle, then widgets on the right."""

    activated = Signal()

    def __init__(self, title, subtitle="", prefix=None, clickable=False, subtitle_lines=1):
        super().__init__()
        self.setObjectName("row")
        self.setProperty("clickable", clickable)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(14, 10, 12, 10)
        self.lay.setSpacing(10)
        self.prefix = prefix
        if prefix is not None:
            self.lay.addWidget(prefix, 0, Qt.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.title_label = ElidedLabel(title, "rowTitle") if subtitle_lines == 1 else label(title, "rowTitle", wrap=True)
        self.subtitle_label = (ElidedLabel(subtitle, "rowSubtitle") if subtitle_lines == 1
                               else label(subtitle, "rowSubtitle", wrap=True))
        self.subtitle_label.setVisible(bool(subtitle))
        text.addWidget(self.title_label)
        text.addWidget(self.subtitle_label)
        self.lay.addLayout(text, 1)
        self.setMinimumHeight(56)

    def get_title(self):
        return self.title_label.text()

    def set_title(self, text):
        if self.title_label.text() != text:
            self.title_label.setText(text)
            self.title_label.update()

    def get_subtitle(self):
        return self.subtitle_label.text()

    def set_subtitle(self, text):
        if self.subtitle_label.text() != text:
            self.subtitle_label.setText(text)
            self.subtitle_label.setVisible(bool(text))
            self.subtitle_label.update()

    def add_suffix(self, widget):
        self.lay.addWidget(widget, 0, Qt.AlignVCenter)

    def mouseReleaseEvent(self, ev):
        if self.property("clickable") and ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.activated.emit()
        super().mouseReleaseEvent(ev)


class SwitchRow(Row):
    def __init__(self, title, subtitle="", active=False):
        super().__init__(title, subtitle, subtitle_lines=2)
        self.switch = Switch(active)
        self.add_suffix(self.switch)

    def get_active(self):
        return self.switch.isChecked()

    def set_active(self, on):
        self.switch.setChecked(on)


class Card(QFrame):
    """A rounded card holding rows, with separators between them."""

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self.rows = []

    def add(self, row):
        if not self.rows:
            row.setStyleSheet("#row { border-top: none; }")
        self.lay.addWidget(row)
        self.rows.append(row)

    def remove(self, row):
        self.rows.remove(row)
        self.lay.removeWidget(row)
        row.deleteLater()
        if self.rows:
            self.rows[0].setStyleSheet("#row { border-top: none; }")


class Group(QWidget):
    """A titled card, like Adw.PreferencesGroup."""

    def __init__(self, title="", description=""):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.title = label(title, "groupTitle")
        self.title.setVisible(bool(title))
        lay.addWidget(self.title)
        self.description = label(description, "groupDescription", wrap=True)
        self.description.setVisible(bool(description))
        lay.addWidget(self.description)
        self.card = Card()
        lay.addWidget(self.card)

    def set_description(self, text):
        self.description.setText(text)
        self.description.setVisible(bool(text))

    def add(self, row):
        self.card.add(row)

    def remove(self, row):
        self.card.remove(row)


class Section(QFrame):
    """A card with a header (icon, title, hint, chevron) and rows below it. Clicking the header
    folds the rows away; folded, the header is the whole card."""

    toggled = Signal(bool)

    def __init__(self, icon, title="", hint="", empty_text="", is_open=True):
        super().__init__()
        self.setObjectName("card")
        self.icon_name = icon
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self.header = QFrame()
        self.header.setObjectName("sectionHeader")
        self.header.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self.header)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(14)
        h.addWidget(image(symbol(icon, theme.LILAC, 20)), 0, Qt.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.title_label = label(title, "sectionTitle")
        self.hint_label = label(hint, "sectionHint", wrap=True)
        text.addWidget(self.title_label)
        text.addWidget(self.hint_label)
        h.addLayout(text, 1)
        self.chevron = image(symbol("expand-more", theme.DIM, 20))
        h.addWidget(self.chevron, 0, Qt.AlignVCenter)
        self.header.mouseReleaseEvent = lambda ev: ev.button() == Qt.LeftButton and self.set_open(not self.is_open)
        self.lay.addWidget(self.header)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(0)
        self.lay.addWidget(self.body)
        self.empty_text = empty_text
        self.empty = label(empty_text, "empty", align=Qt.AlignCenter)
        self.body_lay.addWidget(self.empty)
        self.rows = []
        self.is_open = True
        self.set_open(is_open)

    def set_title(self, text):
        if self.title_label.text() != text:
            self.title_label.setText(text)

    def set_hint(self, text):
        if self.hint_label.text() != text:
            self.hint_label.setText(text)

    def set_open(self, is_open):
        self.is_open = is_open
        self.body.setVisible(is_open)
        self.chevron.setPixmap(symbol("expand-more" if is_open else "expand-less", theme.DIM, 20))
        self.toggled.emit(is_open)

    def add(self, row):
        self.body_lay.addWidget(row)
        self.rows.append(row)

    def insert_sorted(self, row):
        keys = [r.sort_key for r in self.rows]
        i = next((n for n, k in enumerate(keys) if k > row.sort_key), len(keys))
        self.body_lay.insertWidget(i + 1, row)  # after the "empty" label
        self.rows.insert(i, row)

    def take(self, row):
        self.rows.remove(row)
        self.body_lay.removeWidget(row)

    def clear(self):
        for row in self.rows:
            self.body_lay.removeWidget(row)
            row.deleteLater()
        self.rows = []

    def refresh_empty(self, empty_text=None):
        """Shows the placeholder when no row is visible."""
        if empty_text is not None:
            self.empty.setText(empty_text)
        visible = any(not r.isHidden() for r in self.rows)
        self.empty.setVisible(not visible and bool(self.empty.text()))


class Clamp(QWidget):
    """Centres its child and keeps it at most `width` wide (libadwaita's Adw.Clamp)."""

    def __init__(self, child, width=600, margins=(16, 18, 16, 32)):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(*margins)
        lay.addStretch(1)
        child.setMaximumWidth(width)
        child.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(child, 100)
        lay.addStretch(1)


def scroller(child):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(child)
    return area


class StatusPage(QWidget):
    """A centred icon, title, text and optional spinner (libadwaita's Adw.StatusPage)."""

    def __init__(self, icon=None, title="", text="", spinner=False, picture_file=None):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.addStretch(1)
        column = QWidget()
        box = QVBoxLayout(column)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(16)
        if picture_file:
            box.addWidget(image(picture(picture_file, 120)), 0, Qt.AlignHCenter)
        elif icon:
            box.addWidget(image(symbol(icon, "rgba(238,234,247,0.42)", 96)), 0, Qt.AlignHCenter)
        self.title = label(title, "statusTitle", wrap=True, align=Qt.AlignCenter)
        box.addWidget(self.title)
        self.text = label(text, "statusText", wrap=True, align=Qt.AlignCenter, rich=True)
        self.text.setVisible(bool(text))
        box.addWidget(self.text)
        self.extra = QVBoxLayout()
        self.extra.setContentsMargins(0, 8, 0, 0)
        box.addLayout(self.extra)
        if spinner:
            self.extra.addWidget(Spinner(26), 0, Qt.AlignHCenter)
        outer.addWidget(Clamp(column, 460, (0, 0, 0, 0)))
        outer.addStretch(1)

    def set_description(self, text):
        self.text.setText(text)
        self.text.setVisible(bool(text))

    def get_description(self):
        return self.text.text()


def hbox(*widgets, spacing=8, align=None):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for x in widgets:
        if x is None:
            lay.addStretch(1)
        else:
            lay.addWidget(x, 0, align) if align else lay.addWidget(x)
    return w

