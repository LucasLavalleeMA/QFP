#!/usr/bin/env python3
"""
QFP
I love you
"""
import sys
import time
import ctypes
import threading
import os

import numpy as np
import cv2
import mss
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPointF, QRectF, Signal

IS_WIN = sys.platform == "win32"
APP_TITLE = "QFP Gold Edition"
PROJ_TITLE = "QFP"
CTRL = Qt.ControlModifier | Qt.MetaModifier  # Meta so Ctrl works on macOS too


# ----------------------------------------------------------------------------
# Window enumeration / capture helpers
# ----------------------------------------------------------------------------
if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.GetWindowDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    def list_windows():
        """[(hwnd, title)] of visible, non-minimised, titled top-level windows."""
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n == 0:
                return True
            cloaked = wintypes.DWORD(0)  # skip hidden UWP ghost windows
            dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            if cloaked.value:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            found.append((hwnd, buf.value))
            return True

        user32.EnumWindows(cb, 0)
        return found

    def window_rect(hwnd):
        r = wintypes.RECT()
        if not user32.IsWindow(hwnd) or not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
        return r.left, r.top, r.right - r.left, r.bottom - r.top

    def printwindow_grab(hwnd):
        """Grab a window's own pixels (works when it is occluded). Returns BGR."""
        rect = window_rect(hwnd)
        if not rect or rect[2] <= 0 or rect[3] <= 0:
            return None
        w, h = rect[2], rect[3]
        hdc = user32.GetWindowDC(hwnd)
        if not hdc:
            return None
        mem = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        old = gdi32.SelectObject(mem, bmp)
        user32.PrintWindow(hwnd, mem, 2)  # 2 = PW_RENDERFULLCONTENT
        gdi32.SelectObject(mem, old)      # bitmap must be deselected for GetDIBits
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth, bmi.biHeight = w, -h  # negative = top-down
        bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, 0
        buf = (ctypes.c_ubyte * (w * h * 4))()
        gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)
        arr = np.frombuffer(buf, np.uint8).reshape(h, w, 4)
        return np.ascontiguousarray(arr[:, :, :3])
else:
    def list_windows():
        try:
            import pygetwindow as gw
            return [(w, w.title) for w in gw.getAllWindows()
                    if w.title and w.width > 0 and w.height > 0]
        except Exception:
            return []

    def window_rect(win):
        try:
            return win.left, win.top, win.width, win.height
        except Exception:
            return None

    def printwindow_grab(_h):
        return None

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ----------------------------------------------------------------------------
# Capture sources (one thread each; main thread only reads the latest frame)
# ----------------------------------------------------------------------------
class Source:
    FPS = 30

    def __init__(self, name, size):
        self.name = name
        self.size = size  # (w, h) hint used for the initial layer shape
        self._frame = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def latest(self):
        with self._lock:
            return self._frame

    def _loop(self):
        sct = mss.mss()  # mss instances are per-thread
        self._sct = sct
        period = 1.0 / self.FPS
        try:
            while not self._stop.is_set():
                t0 = time.perf_counter()
                try:
                    frame = self._grab()
                    if frame is not None:
                        with self._lock:
                            self._frame = frame
                except Exception:
                    pass  # e.g. window closed / minimised; keep last frame
                self._stop.wait(max(0.0, period - (time.perf_counter() - t0)))
        finally:
            sct.close()

    def _grab_region(self, region):
        shot = self._sct.grab(region)
        arr = np.frombuffer(shot.bgra, np.uint8).reshape(shot.height, shot.width, 4)
        return np.ascontiguousarray(arr[:, :, :3])


class MonitorSource(Source):
    def __init__(self, index, mon):
        super().__init__(f"Screen {index}", (mon["width"], mon["height"]))
        self.mon = dict(mon)

    def _grab(self):
        return self._grab_region(self.mon)


class WindowSource(Source):
    def __init__(self, title, handle, use_printwindow):
        rect = window_rect(handle) or (0, 0, 1280, 720)
        super().__init__(title[:40], (max(rect[2], 2), max(rect[3], 2)))
        self.handle = handle
        self.use_printwindow = use_printwindow and IS_WIN

    def _grab(self):
        if self.use_printwindow:
            return printwindow_grab(self.handle)
        rect = window_rect(self.handle)
        if not rect or rect[2] <= 0 or rect[3] <= 0:
            return None
        l, t, w, h = rect
        return self._grab_region({"left": l, "top": t, "width": w, "height": h})


# ----------------------------------------------------------------------------
# Scene model + compositor
# ----------------------------------------------------------------------------
class Layer:
    def __init__(self, source, canvas_size):
        self.source = source
        self.visible = True
        self.quad = self.default_quad(canvas_size)  # TL, TR, BR, BL in canvas px

    def default_quad(self, canvas_size):
        cw, ch = canvas_size
        sw, sh = self.source.size
        s = min(cw * 0.5 / sw, ch * 0.5 / sh)
        w, h = sw * s, sh * s
        x0, y0 = (cw - w) / 2, (ch - h) / 2
        return np.array([[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]], float)

    def reset(self, canvas_size):
        self.quad = self.default_quad(canvas_size)

    def contains(self, pt):
        poly = QtGui.QPolygonF([QPointF(x, y) for x, y in self.quad])
        return poly.containsPoint(QPointF(pt[0], pt[1]), Qt.OddEvenFill)


class Scene:
    def __init__(self):
        self.size = (1920, 1080)
        self.layers = []  # index 0 = back, last = front
        self.selected = None
        self.canvas = np.zeros((1080, 1920, 3), np.uint8)

    def set_size(self, w, h):
        ow, oh = self.size
        if (w, h) == (ow, oh):
            return
        for l in self.layers:
            l.quad *= np.array([w / ow, h / oh])
        self.size = (w, h)
        self.canvas = np.zeros((h, w, 3), np.uint8)


def compose(scene):
    """Perspective-warp every visible layer into scene.canvas (BGR)."""
    cw, ch = scene.size
    canvas = scene.canvas
    canvas[:] = 0
    for layer in scene.layers:
        if not layer.visible:
            continue
        frame = layer.source.latest()
        if frame is None:
            continue
        q = layer.quad
        x0 = max(int(np.floor(q[:, 0].min())), 0)
        x1 = min(int(np.ceil(q[:, 0].max())) + 1, cw)
        y0 = max(int(np.floor(q[:, 1].min())), 0)
        y1 = min(int(np.ceil(q[:, 1].max())) + 1, ch)
        if x1 <= x0 or y1 <= y0:
            continue

        h, w = frame.shape[:2]
        # Pre-shrink with area averaging when the quad is much smaller than the
        # source: nicer quality (no aliasing) and cheaper to warp.
        tw = int(np.ceil(max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[3]))))
        th = int(np.ceil(max(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1]))))
        if tw < w or th < h:
            frame = cv2.resize(frame, (max(2, min(w, tw)), max(2, min(h, th))),
                               interpolation=cv2.INTER_AREA)
            h, w = frame.shape[:2]

        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = (q - (x0, y0)).astype(np.float32)
        try:
            M = cv2.getPerspectiveTransform(src, dst)
        except cv2.error:
            continue
        rw, rh = x1 - x0, y1 - y0
        warped = cv2.warpPerspective(frame, M, (rw, rh), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REPLICATE)
        mask = np.zeros((rh, rw), np.uint8)
        cv2.fillPoly(mask, [np.rint(dst).astype(np.int32)], 255)
        np.copyto(canvas[y0:y1, x0:x1], warped, where=(mask > 0)[:, :, None])


# ----------------------------------------------------------------------------
# Projector (fullscreen output) window
# ----------------------------------------------------------------------------
class ProjectorWindow(QtWidgets.QWidget):
    closed = Signal()

    def __init__(self, scene):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.scene = scene
        self.qimg = None
        self.guides = False
        self.setWindowTitle(PROJ_TITLE)
        self.setCursor(Qt.BlankCursor)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def show_on(self, screen):
        self.setGeometry(screen.geometry())
        self.show()
        if self.windowHandle():
            self.windowHandle().setScreen(screen)
        self.setGeometry(screen.geometry())
        self.showFullScreen()
        if IS_WIN:  # keep this window out of screen captures -> no feedback loop
            try:
                user32.SetWindowDisplayAffinity(int(self.winId()), 0x11)
            except Exception:
                pass

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        if self.qimg is not None:
            p.drawImage(self.rect(), self.qimg)
        if self.guides:
            cw, ch = self.scene.size
            p.scale(self.width() / cw, self.height() / ch)
            for layer in self.scene.layers:
                if not layer.visible:
                    continue
                sel = layer is self.scene.selected
                pen = QtGui.QPen(QtGui.QColor(255, 200, 0) if sel else QtGui.QColor(0, 200, 255))
                pen.setWidth(2)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawPolygon(QtGui.QPolygonF([QPointF(x, y) for x, y in layer.quad]))
                if sel:
                    p.setBrush(QtGui.QColor(255, 200, 0))
                    for x, y in layer.quad:
                        p.drawEllipse(QPointF(x, y), 8, 8)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)


# ----------------------------------------------------------------------------
# Preview pane with draggable pins / layers
# ----------------------------------------------------------------------------
class PreviewWidget(QtWidgets.QWidget):
    selectionChanged = Signal()
    PIN_R = 8

    def __init__(self, scene):
        super().__init__()
        self.scene = scene
        self.fine = 0.1       # mouse-movement multiplier while CTRL is held
        self.qimg = None
        self.drag = None
        self.active_pin = None
        self.hover_pin = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(480, 270)

    # -- coordinate mapping (canvas px <-> widget px) --
    def _xform(self):
        cw, ch = self.scene.size
        s = min(self.width() / cw, self.height() / ch)
        return s, (self.width() - cw * s) / 2, (self.height() - ch * s) / 2

    def to_widget(self, pt):
        s, ox, oy = self._xform()
        return QPointF(pt[0] * s + ox, pt[1] * s + oy)

    def to_canvas(self, pos):
        s, ox, oy = self._xform()
        return ((pos.x() - ox) / s, (pos.y() - oy) / s)

    # -- hit testing --
    def _pin_at(self, pos):
        sel = self.scene.selected
        if sel is None:
            return None
        best, best_d = None, self.PIN_R + 5
        for i, pt in enumerate(sel.quad):
            c = self.to_widget(pt)
            d = np.hypot(pos.x() - c.x(), pos.y() - c.y())
            if d <= best_d:
                best, best_d = i, d
        return best

    def _layer_at(self, pos):
        pt = self.to_canvas(pos)
        for layer in reversed(self.scene.layers):
            if layer.visible and layer.contains(pt):
                return layer
        return None

    def select(self, layer):
        if layer is not self.scene.selected:
            self.active_pin = None
        self.scene.selected = layer
        self.selectionChanged.emit()
        self.update()

    # -- painting --
    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(24, 24, 24))
        s, ox, oy = self._xform()
        cw, ch = self.scene.size
        target = QRectF(ox, oy, cw * s, ch * s)
        if self.qimg is not None:
            p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
            p.drawImage(target, self.qimg)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtGui.QPen(QtGui.QColor(90, 90, 90), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(target)

        for layer in self.scene.layers:
            if not layer.visible:
                continue
            sel = layer is self.scene.selected
            col = QtGui.QColor(255, 200, 0) if sel else QtGui.QColor(0, 200, 255, 170)
            p.setPen(QtGui.QPen(col, 2 if sel else 1))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(QtGui.QPolygonF([self.to_widget(pt) for pt in layer.quad]))
            tl = self.to_widget(layer.quad[0])
            p.drawText(QPointF(tl.x() + 4, tl.y() - 6), layer.source.name)

        sel = self.scene.selected
        if sel is not None and sel.visible:
            for i, pt in enumerate(sel.quad):
                c = self.to_widget(pt)
                r = self.PIN_R + (2 if i == self.hover_pin else 0)
                p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 2))
                p.setBrush(QtGui.QColor(255, 70, 70) if i == self.active_pin
                           else QtGui.QColor(255, 200, 0))
                p.drawEllipse(c, r, r)
                p.setPen(QtGui.QColor(0, 0, 0))
                p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, str(i + 1))

    # -- mouse --
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self.setFocus()
        pos = e.position()
        sel = self.scene.selected

        pin = self._pin_at(pos)
        if pin is not None:
            self.active_pin = pin
            self.drag = {"kind": "pin", "layer": sel, "idx": pin, "last": pos}
            self.update()
            return

        hit = self._layer_at(pos)
        # SHIFT-press on the already selected layer keeps it (even if overlapped)
        if (e.modifiers() & Qt.ShiftModifier) and sel and sel.visible and sel.contains(self.to_canvas(pos)):
            hit = sel
        self.select(hit)
        self.drag = {"kind": "layer", "layer": hit, "last": pos} if hit else None

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self.drag is None or not (e.buttons() & Qt.LeftButton):
            hp = self._pin_at(pos)
            if hp != self.hover_pin:
                self.hover_pin = hp
                self.update()
            if hp is not None:
                self.setCursor(Qt.CrossCursor)
            elif (e.modifiers() & Qt.ShiftModifier) and self._layer_at(pos):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.unsetCursor()
            return

        d = self.drag
        last = d["last"]
        d["last"] = pos  # always advance, so toggling modifiers never causes a jump
        mods = e.modifiers()
        factor = self.fine if (mods & CTRL) else 1.0
        scale = self._xform()[0]
        delta = np.array([pos.x() - last.x(), pos.y() - last.y()]) / scale * factor
        if d["kind"] == "pin":
            d["layer"].quad[d["idx"]] += delta
        elif mods & Qt.ShiftModifier:  # layer drags require SHIFT
            d["layer"].quad += delta
        self.update()

    def mouseReleaseEvent(self, _e):
        self.drag = None

    # -- keyboard nudging --
    def keyPressEvent(self, e):
        sel = self.scene.selected
        key = e.key()
        if key == Qt.Key_Escape:
            self.select(None)
            return
        if sel is None:
            return super().keyPressEvent(e)
        if Qt.Key_1 <= key <= Qt.Key_4:
            self.active_pin = key - Qt.Key_1
            self.update()
            return
        dirs = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        if key in dirs:
            mods = e.modifiers()
            step = 10.0 if mods & Qt.ShiftModifier else (0.1 if mods & CTRL else 1.0)
            delta = np.array(dirs[key], float) * step
            if self.active_pin is not None:
                sel.quad[self.active_pin] += delta
            else:
                sel.quad += delta
            self.update()
            return
        super().keyPressEvent(e)


# ----------------------------------------------------------------------------
# Window picker dialog
# ----------------------------------------------------------------------------
class WindowPicker(QtWidgets.QDialog):
    def __init__(self, parent, exclude_titles):
        super().__init__(parent)
        self.setWindowTitle("Add window")
        self.resize(460, 420)
        self.exclude = set(exclude_titles)
        lay = QtWidgets.QVBoxLayout(self)
        self.list = QtWidgets.QListWidget()
        lay.addWidget(self.list)
        self.screen_chk = QtWidgets.QCheckBox(
            "Capture from screen instead of the window itself\n"
            "(use if the window comes out black; it must stay visible)")
        if not IS_WIN:
            self.screen_chk.setChecked(True)
            self.screen_chk.setEnabled(False)
        lay.addWidget(self.screen_chk)
        row = QtWidgets.QHBoxLayout()
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.clicked.connect(self.populate)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        row.addWidget(refresh)
        row.addStretch()
        row.addWidget(bb)
        lay.addLayout(row)
        self.list.itemDoubleClicked.connect(lambda *_: self.accept())
        self.items = []
        self.populate()

    def populate(self):
        self.list.clear()
        self.items = [(h, t) for h, t in list_windows() if t not in self.exclude]
        for _h, t in self.items:
            self.list.addItem(t)

    def choice(self):
        row = self.list.currentRow()
        if row < 0:
            return None
        h, t = self.items[row]
        return h, t, self.screen_chk.isChecked()


# ----------------------------------------------------------------------------
# Main control window
# ----------------------------------------------------------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.scene = Scene()
        self.projector = ProjectorWindow(self.scene)
        self.projector.closed.connect(lambda: self.proj_btn.setChecked(False))
        self.preview = PreviewWidget(self.scene)
        self.preview.selectionChanged.connect(self.sync_list_selection)

        side = QtWidgets.QWidget()
        side.setFixedWidth(330)
        v = QtWidgets.QVBoxLayout(side)

        # --- projector group
        g = QtWidgets.QGroupBox("Projector output")
        gl = QtWidgets.QVBoxLayout(g)
        self.screens = QtGui.QGuiApplication.screens()
        primary = QtGui.QGuiApplication.primaryScreen()
        self.screen_combo = QtWidgets.QComboBox()
        for i, s in enumerate(self.screens):
            w, h = self.screen_px(s)
            self.screen_combo.addItem(f"{i + 1}: {s.name()}  {w}x{h}" + ("  (primary)" if s == primary else ""))
        self.screen_combo.setCurrentIndex(next((i for i, s in enumerate(self.screens) if s != primary), 0))
        self.screen_combo.currentIndexChanged.connect(self.on_screen_changed)
        self.proj_btn = QtWidgets.QPushButton("Start projector output")
        self.proj_btn.setCheckable(True)
        self.proj_btn.toggled.connect(self.on_proj_toggled)
        self.guides_chk = QtWidgets.QCheckBox("Show outlines + pins on projector")
        self.guides_chk.toggled.connect(lambda on: setattr(self.projector, "guides", on))
        gl.addWidget(self.screen_combo)
        gl.addWidget(self.proj_btn)
        gl.addWidget(self.guides_chk)
        v.addWidget(g)

        # --- sources group
        g = QtWidgets.QGroupBox("Add sources")
        gl = QtWidgets.QHBoxLayout(g)
        self.screen_menu = QtWidgets.QMenu(self)
        self.screen_menu.aboutToShow.connect(self.populate_screen_menu)
        add_screen = QtWidgets.QPushButton("Add screen...")
        add_screen.setMenu(self.screen_menu)
        add_window = QtWidgets.QPushButton("Add window...")
        add_window.clicked.connect(self.add_window)
        gl.addWidget(add_screen)
        gl.addWidget(add_window)
        v.addWidget(g)

        # --- layers group
        g = QtWidgets.QGroupBox("Layers (top = front)")
        gl = QtWidgets.QVBoxLayout(g)
        self.list = QtWidgets.QListWidget()
        self.list.currentRowChanged.connect(self.on_list_row)
        self.list.itemChanged.connect(self.on_item_changed)
        gl.addWidget(self.list)
        row = QtWidgets.QHBoxLayout()
        for text, fn in (("Raise", lambda: self.move_layer(+1)), ("Lower", lambda: self.move_layer(-1)),
                         ("Reset pins", self.reset_layer), ("Remove", self.remove_layer)):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        gl.addLayout(row)
        v.addWidget(g, 1)

        # --- precision
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("CTRL fine-mode speed:"))
        self.fine_spin = QtWidgets.QDoubleSpinBox()
        self.fine_spin.setRange(0.01, 1.0)
        self.fine_spin.setSingleStep(0.05)
        self.fine_spin.setDecimals(2)
        self.fine_spin.setSuffix(" x")
        self.fine_spin.setValue(0.1)
        self.fine_spin.valueChanged.connect(lambda val: setattr(self.preview, "fine", val))
        row.addWidget(self.fine_spin)
        v.addLayout(row)

        help_lbl = QtWidgets.QLabel(
            "<b>Preview controls</b><br>"
            "Click layer: select<br>"
            "Drag pin: move corner<br>"
            "<b>Shift</b>+drag layer: move layer<br>"
            "<b>Ctrl</b> held: fine movement<br>"
            "Arrows: nudge (Shift 10px, Ctrl 0.1px)<br>"
            "1-4: choose pin &nbsp; Esc: deselect<br>"
            "Esc on projector: close it")
        help_lbl.setWordWrap(True)
        v.addWidget(help_lbl)

        license_label = QtWidgets.QLabel()

        license_label.setText(
            'This application is built using PySide6. '
            'The PySide6/Qt framework is licensed under the '
            '<a href="https://gnu.org" style="color: #0066cc;">GNU LGPLv3</a>. '
            'You can view the full Qt licensing terms on the '
            '<a href="https://qt.io" style="color: #0066cc;">Qt Licensing Page</a>.'
        )
        v.addWidget(license_label)
        license_label.setStyleSheet("color: gray;") 

        license_label.setOpenExternalLinks(True)
        license_label.setWordWrap(True)
        license_label.setTextInteractionFlags(
            license_label.textInteractionFlags() | 
            license_label.textInteractionFlags().TextSelectableByMouse
        )
        central = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(central)
        h.addWidget(self.preview, 1)
        h.addWidget(side)
        self.setCentralWidget(central)
        self.resize(1280, 720)

        icon_path = get_resource_path("favicon.ico")
        self.setWindowIcon(QtGui.QIcon(icon_path))

        self.apply_screen_size()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        

    # -- screens / projector --
    @staticmethod
    def screen_px(s):
        dpr = s.devicePixelRatio()
        return round(s.size().width() * dpr), round(s.size().height() * dpr)

    def current_screen(self):
        return self.screens[self.screen_combo.currentIndex()]

    def apply_screen_size(self):
        w, h = self.screen_px(self.current_screen())
        self.preview.qimg = None  # drop images that reference the old canvas buffer
        self.projector.qimg = None
        self.scene.set_size(w, h)
        self.preview.update()

    def on_screen_changed(self, _i):
        self.apply_screen_size()
        if self.projector.isVisible():
            self.projector.hide()
            self.projector.show_on(self.current_screen())

    def on_proj_toggled(self, on):
        self.proj_btn.setText("Stop projector output" if on else "Start projector output")
        if on:
            self.projector.show_on(self.current_screen())
        else:
            self.projector.hide()

    # -- sources / layers --
    def populate_screen_menu(self):
        self.screen_menu.clear()
        with mss.mss() as sct:
            mons = [dict(m) for m in sct.monitors[1:]]
        for i, m in enumerate(mons, 1):
            act = self.screen_menu.addAction(f"Monitor {i}: {m['width']}x{m['height']} at ({m['left']}, {m['top']})")
            act.triggered.connect(lambda _=False, i=i, m=m: self.add_source(MonitorSource(i, m)))

    def add_window(self):
        dlg = WindowPicker(self, {APP_TITLE, PROJ_TITLE})
        if dlg.exec():
            ch = dlg.choice()
            if ch:
                handle, title, use_screen = ch
                self.add_source(WindowSource(title, handle, use_printwindow=not use_screen))

    def add_source(self, src):
        src.start()
        layer = Layer(src, self.scene.size)
        self.scene.layers.append(layer)
        self.refresh_list()
        self.preview.select(layer)

    def layer_at_row(self, row):
        n = len(self.scene.layers)
        return self.scene.layers[n - 1 - row] if 0 <= row < n else None

    def refresh_list(self):
        self.list.blockSignals(True)
        self.list.clear()
        for layer in reversed(self.scene.layers):
            it = QtWidgets.QListWidgetItem(layer.source.name)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self.sync_list_selection()

    def sync_list_selection(self):
        layers, sel = self.scene.layers, self.scene.selected
        row = len(layers) - 1 - layers.index(sel) if sel in layers else -1
        self.list.blockSignals(True)
        self.list.setCurrentRow(row)
        self.list.blockSignals(False)

    def on_list_row(self, row):
        self.preview.select(self.layer_at_row(row))

    def on_item_changed(self, item):
        layer = self.layer_at_row(self.list.row(item))
        if layer:
            layer.visible = item.checkState() == Qt.Checked
            self.preview.update()

    def move_layer(self, direction):
        layers, sel = self.scene.layers, self.scene.selected
        if sel is None:
            return
        i = layers.index(sel)
        j = i + direction
        if 0 <= j < len(layers):
            layers[i], layers[j] = layers[j], layers[i]
            self.refresh_list()

    def reset_layer(self):
        if self.scene.selected:
            self.scene.selected.reset(self.scene.size)
            self.preview.update()

    def remove_layer(self):
        sel = self.scene.selected
        if sel is None:
            return
        sel.source.stop()
        self.scene.layers.remove(sel)
        self.preview.select(None)
        self.refresh_list()

    # -- render loop --
    def tick(self):
        compose(self.scene)
        cw, ch = self.scene.size
        c = self.scene.canvas
        img = QtGui.QImage(c.data, cw, ch, c.strides[0], QtGui.QImage.Format_BGR888)
        self.preview.qimg = img
        self.preview.update()
        if self.projector.isVisible():
            self.projector.qimg = img
            self.projector.update()

    def closeEvent(self, e):
        self.timer.stop()
        for layer in self.scene.layers:
            layer.source.stop()
        self.projector.hide()
        super().closeEvent(e)
        QtWidgets.QApplication.quit()


def main():
    try:
        myappid = "qfp.goldedition.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()