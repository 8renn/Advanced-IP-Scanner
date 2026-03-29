import ctypes
import subprocess
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GWL_STYLE = -16
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_SETTEXT = 0x000C
MAPVK_VK_TO_VSC = 0

if ctypes.sizeof(ctypes.c_void_p) == 8:
    _GetWindowLong = _user32.GetWindowLongPtrW
    _SetWindowLong = _user32.SetWindowLongPtrW
else:
    _GetWindowLong = _user32.GetWindowLongW
    _SetWindowLong = _user32.SetWindowLongW
_GetWindowLong.argtypes = (wintypes.HWND, ctypes.c_int)
_GetWindowLong.restype = getattr(wintypes, "LONG_PTR", ctypes.c_longlong)
_SetWindowLong.argtypes = (wintypes.HWND, ctypes.c_int, _GetWindowLong.restype)
_SetWindowLong.restype = _GetWindowLong.restype

_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD

_user32.IsWindowVisible.argtypes = (wintypes.HWND,)
_user32.IsWindowVisible.restype = wintypes.BOOL

_user32.GetParent.argtypes = (wintypes.HWND,)
_user32.GetParent.restype = wintypes.HWND

_user32.SetParent.argtypes = (wintypes.HWND, wintypes.HWND)
_user32.SetParent.restype = wintypes.HWND

_user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.c_void_p)
_user32.GetClientRect.restype = wintypes.BOOL

_user32.SetWindowPos.argtypes = (
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
)
_user32.SetWindowPos.restype = wintypes.BOOL

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = (_WNDENUMPROC, wintypes.LPARAM)
_user32.EnumWindows.restype = wintypes.BOOL

_user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
_user32.SetForegroundWindow.restype = wintypes.BOOL

_user32.SetFocus.argtypes = (wintypes.HWND,)
_user32.SetFocus.restype = wintypes.HWND

_kernel32.GetCurrentThreadId.argtypes = ()
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD

_user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
_user32.AttachThreadInput.restype = wintypes.BOOL

_CHILDWNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumChildWindows.argtypes = (wintypes.HWND, _CHILDWNDENUMPROC, wintypes.LPARAM)
_user32.EnumChildWindows.restype = wintypes.BOOL

_user32.GetClassNameW.argtypes = (wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int)
_user32.GetClassNameW.restype = ctypes.c_int

_user32.IsWindow.argtypes = (wintypes.HWND,)
_user32.IsWindow.restype = wintypes.BOOL

_user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
_user32.MapVirtualKeyW.restype = wintypes.UINT

_user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.SendMessageW.restype = getattr(wintypes, "LRESULT", ctypes.c_ssize_t)

_user32.FindWindowExW.argtypes = (
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
)
_user32.FindWindowExW.restype = wintypes.HWND

_user32.GetWindowTextW.argtypes = (wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int)
_user32.GetWindowTextW.restype = ctypes.c_int


class _RECT(ctypes.Structure):
    _fields_ = (
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    )


def _get_window_thread_process_id(hwnd: int) -> tuple[int, int]:
    pid = wintypes.DWORD()
    tid = _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(tid), int(pid.value)


def _apply_input_focus_to_embedded(parent_hwnd: int, focus_hwnd: int | None = None) -> None:
    focus = focus_hwnd if focus_hwnd is not None else parent_hwnd
    winmtr_tid, _ = _get_window_thread_process_id(parent_hwnd)
    cur_tid = int(_kernel32.GetCurrentThreadId())
    _user32.AttachThreadInput(cur_tid, winmtr_tid, True)
    try:
        _user32.SetForegroundWindow(parent_hwnd)
        _user32.SetFocus(focus)
    finally:
        _user32.AttachThreadInput(cur_tid, winmtr_tid, False)


def _key_scan_extended(event: QKeyEvent, vk: int) -> tuple[int, int]:
    scan = int(event.nativeScanCode()) & 0xFF
    if scan == 0 and vk:
        scan = int(_user32.MapVirtualKeyW(vk & 0xFF, MAPVK_VK_TO_VSC)) & 0xFF
    ext = 1 if int(event.nativeScanCode()) > 0xFF else 0
    return scan, ext


def _key_lparam(scan: int, extended: int, key_up: bool) -> int:
    lp = 1 | ((scan & 0xFF) << 16) | ((extended & 1) << 24)
    if key_up:
        lp |= (1 << 30) | (1 << 31)
    return lp


def _forward_keypress_to_edit(edit_hwnd: int, event: QKeyEvent) -> None:
    vk = int(event.nativeVirtualKey()) & 0xFF
    if vk == 0:
        return
    scan, ext = _key_scan_extended(event, vk)
    lp_down = _key_lparam(scan, ext, False)
    lp_up = _key_lparam(scan, ext, True)

    _user32.SendMessageW(edit_hwnd, WM_KEYDOWN, vk, lp_down)

    chars = list(event.text())
    if not chars:
        k = event.key()
        if k == Qt.Key.Key_Backspace:
            chars = ["\x08"]
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            chars = ["\r"]
        elif k == Qt.Key.Key_Tab:
            chars = ["\t"]

    for ch in chars:
        _user32.SendMessageW(edit_hwnd, WM_CHAR, ord(ch), lp_down)

    _user32.SendMessageW(edit_hwnd, WM_KEYUP, vk, lp_up)


def _find_host_edit_hwnd(root_hwnd: int) -> int | None:
    buf = ctypes.create_unicode_buffer(256)
    found: list[int] = []

    @_CHILDWNDENUMPROC
    def _enum_child(child: int, _lp: int) -> bool:
        if found:
            return False
        n = _user32.GetClassNameW(child, buf, 256)
        if n > 0 and buf.value == "Edit":
            found.append(int(child))
            return False
        _user32.EnumChildWindows(child, _enum_child, 0)
        return False if found else True

    _user32.EnumChildWindows(root_hwnd, _enum_child, 0)
    return found[0] if found else None


def _find_button_by_text(root_hwnd: int, caption: str) -> int | None:
    tbuf = ctypes.create_unicode_buffer(256)
    cbuf = ctypes.create_unicode_buffer(256)
    found: list[int] = []

    @_CHILDWNDENUMPROC
    def _enum_child(child: int, _lp: int) -> bool:
        if found:
            return False
        nc = _user32.GetClassNameW(child, cbuf, 256)
        if nc > 0 and cbuf.value == "Button":
            nt = _user32.GetWindowTextW(child, tbuf, 256)
            if nt > 0 and tbuf.value.strip() == caption:
                found.append(int(child))
                return False
        _user32.EnumChildWindows(child, _enum_child, 0)
        return False if found else True

    _user32.EnumChildWindows(root_hwnd, _enum_child, 0)
    return found[0] if found else None


def _find_direct_edit_under(parent_hwnd: int) -> int | None:
    nxt = _user32.FindWindowExW(parent_hwnd, None, "Edit", None)
    return int(nxt) if nxt else None


def _enum_windows_find_top_level(pid: int) -> int | None:
    found: list[int] = []

    @_WNDENUMPROC
    def _cb(hwnd: int, _lp: int) -> bool:
        if not _user32.IsWindowVisible(hwnd):
            return True
        _, wpid = _get_window_thread_process_id(hwnd)
        if wpid != pid:
            return True
        if _user32.GetParent(hwnd):
            return True
        found.append(int(hwnd))
        return True

    _user32.EnumWindows(_cb, 0)
    return found[0] if found else None


class MTRView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._proc: subprocess.Popen[bytes] | None = None
        self._child_hwnd: int | None = None
        self.edit_hwnd: int | None = None
        self._embed_timer: QTimer | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._container = QFrame(self)
        self._container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._container.setAttribute(Qt.WA_NativeWindow, True)
        self._container.installEventFilter(self)

        self.overlay = QWidget(self._container)
        self.overlay.setStyleSheet(
            """
            background-color: rgba(59, 95, 163, 60);
            border-radius: 6px;
            """
        )
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.overlay.setGeometry(0, 0, self._container.width(), self._container.height())

        root_layout.addWidget(self._container, 1)

        self._launch_winmtr()

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def _launch_winmtr(self) -> None:
        exe = self._project_root() / "WinMTR.exe"
        if not exe.is_file():
            return
        try:
            self._proc = subprocess.Popen(
                [str(exe)],
                cwd=str(self._project_root()),
            )
        except OSError:
            self._proc = None
            return

        self._embed_timer = QTimer(self)
        self._embed_timer.timeout.connect(self._try_embed)
        self._embed_timer.start(100)

    def _find_winmtr_hwnd(self, pid: int) -> int | None:
        return _enum_windows_find_top_level(pid)

    def _try_embed(self) -> None:
        if self._proc is None:
            if self._embed_timer:
                self._embed_timer.stop()
            return

        if self._proc.poll() is not None:
            if self._embed_timer:
                self._embed_timer.stop()
            if self._child_hwnd is None:
                print("WinMTR window not found")
            return

        hwnd = self._find_winmtr_hwnd(self._proc.pid)
        if hwnd is None:
            return

        container_hwnd = int(self._container.winId())
        if container_hwnd == 0:
            return

        if self._embed_timer:
            self._embed_timer.stop()

        _user32.SetParent(hwnd, container_hwnd)

        w, h = self._embed_target_size_px()
        _user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            w,
            h,
            SWP_NOZORDER | SWP_SHOWWINDOW,
        )

        style = int(_GetWindowLong(hwnd, GWL_STYLE))
        style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        _SetWindowLong(hwnd, GWL_STYLE, style)

        self._child_hwnd = hwnd
        self._resize_embedded()

        self.edit_hwnd = _find_host_edit_hwnd(hwnd)
        _apply_input_focus_to_embedded(hwnd, self.edit_hwnd)
        self.overlay.resize(self._container.size())
        self.overlay.raise_()

    def _embed_target_size_px(self) -> tuple[int, int]:
        w = int(self._container.width())
        h = int(self._container.height())
        if w > 0 and h > 0:
            return w, h
        container_hwnd = int(self._container.winId())
        r = _RECT()
        if container_hwnd and _user32.GetClientRect(container_hwnd, ctypes.byref(r)):
            cw = int(r.right - r.left)
            ch = int(r.bottom - r.top)
            if cw > 0 and ch > 0:
                return cw, ch
        return 1, 1

    def _resize_embedded(self) -> None:
        if self._child_hwnd is None:
            return
        w, h = self._embed_target_size_px()
        _user32.SetWindowPos(
            self._child_hwnd,
            0,
            0,
            0,
            w,
            h,
            SWP_NOZORDER | SWP_SHOWWINDOW | SWP_FRAMECHANGED,
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.overlay.resize(self._container.size())
        self.overlay.raise_()
        self._resize_embedded()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            not self.isVisible()
            or not self.edit_hwnd
            or not _user32.IsWindow(self.edit_hwnd)
        ):
            super().keyPressEvent(event)
            return
        if (int(event.nativeVirtualKey()) & 0xFF) == 0:
            super().keyPressEvent(event)
            return
        _forward_keypress_to_edit(self.edit_hwnd, event)
        event.accept()

    def set_host(self, host: str) -> None:
        root = self._child_hwnd
        if root is None or not _user32.IsWindow(root):
            return

        cbuf = ctypes.create_unicode_buffer(256)
        combo_hw: list[int] = []

        @_CHILDWNDENUMPROC
        def _cb(child: int, _lp: int) -> bool:
            if combo_hw:
                return False
            nc = _user32.GetClassNameW(child, cbuf, 256)
            if nc > 0 and cbuf.value == "ComboBox":
                combo_hw.append(int(child))
                return False
            return True

        _user32.EnumChildWindows(root, _cb, 0)
        if not combo_hw:
            return

        combo_hwnd = combo_hw[0]
        text_buf = ctypes.create_unicode_buffer(host)
        _user32.SendMessageW(combo_hwnd, WM_SETTEXT, 0, ctypes.addressof(text_buf))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._container and event.type() == QEvent.Type.MouseButtonPress:
            if self._child_hwnd is not None:
                _apply_input_focus_to_embedded(self._child_hwnd, self.edit_hwnd)
        return super().eventFilter(watched, event)


MTRWidget = MTRView
