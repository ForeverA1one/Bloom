"""
Низкоуровневый слой Win32 (ctypes): перечисление мониторов, DDC/CI,
затемняющий оверлей, оформление окна.

Никаких внешних зависимостей — только стандартная библиотека.
"""

from __future__ import annotations

import ctypes
import math
import threading
import time
from ctypes import wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)

LPARAM = wt.LPARAM
WPARAM = wt.WPARAM
LRESULT = ctypes.c_longlong
HANDLE = wt.HANDLE
HWND = wt.HWND
HDC = wt.HDC
UINT = wt.UINT
DWORD = wt.DWORD
BOOL = wt.BOOL
LONG = wt.LONG
WORD = wt.WORD
ULONG_PTR = ctypes.c_size_t

MONITORENUMPROC = ctypes.WINFUNCTYPE(BOOL, HANDLE, HDC, ctypes.POINTER(wt.RECT), LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

# ---------------------------------------------------------------- структуры


class RECT(ctypes.Structure):
    _fields_ = [("left", LONG), ("top", LONG), ("right", LONG), ("bottom", LONG)]

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", DWORD),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("DeviceName", wt.WCHAR * 32),
        ("DeviceString", wt.WCHAR * 128),
        ("StateFlags", DWORD),
        ("DeviceID", wt.WCHAR * 128),
        ("DeviceKey", wt.WCHAR * 128),
    ]


class POINTL(ctypes.Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class DEVMODE(ctypes.Structure):
    """WCHAR dmDeviceName[32]; ... (упрощённая, но совместимая раскладка)."""

    _fields_ = [
        ("dmDeviceName", wt.WCHAR * 32),
        ("dmSpecVersion", WORD),
        ("dmDriverVersion", WORD),
        ("dmSize", WORD),
        ("dmDriverExtra", WORD),
        ("dmFields", DWORD),
        ("dmPosition", POINTL),
        ("dmDisplayOrientation", DWORD),
        ("dmDisplayFixedOutput", DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wt.WCHAR * 32),
        ("dmLogPixels", WORD),
        ("dmBitsPerPel", DWORD),
        ("dmPelsWidth", DWORD),
        ("dmPelsHeight", DWORD),
        ("dmDisplayFlags", DWORD),
        ("dmDisplayFrequency", DWORD),
        ("dmICMMethod", DWORD),
        ("dmICMIntent", DWORD),
        ("dmMediaType", DWORD),
        ("dmDitherType", DWORD),
        ("dmReserved1", DWORD),
        ("dmReserved2", DWORD),
        ("dmPanningWidth", DWORD),
        ("dmPanningHeight", DWORD),
    ]


class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", UINT),
        ("style", UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HANDLE),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", DWORD), ("biWidth", LONG), ("biHeight", LONG),
        ("biPlanes", WORD), ("biBitCount", WORD), ("biCompression", DWORD),
        ("biSizeImage", DWORD), ("biXPelsPerMeter", LONG), ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD), ("biClrImportant", DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", DWORD * 3)]


class NMHDR(ctypes.Structure):
    _fields_ = [("hwndFrom", HWND), ("idFrom", ULONG_PTR), ("code", UINT)]


class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [("hPhysicalMonitor", HANDLE),
                ("szPhysicalMonitorDescription", wt.WCHAR * 128)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", DWORD), ("hWnd", HWND), ("uID", UINT), ("uFlags", UINT),
        ("uCallbackMessage", UINT), ("hIcon", HANDLE), ("szTip", wt.WCHAR * 128),
        ("dwState", DWORD), ("dwStateMask", DWORD), ("szInfo", wt.WCHAR * 256),
        ("uTimeoutOrVersion", UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", DWORD),
        ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", HANDLE),
    ]


# -------------------------------------------------------------- прототипы

user32.EnumDisplayMonitors.argtypes = [HDC, ctypes.POINTER(RECT), MONITORENUMPROC, LPARAM]
user32.EnumDisplayMonitors.restype = BOOL
user32.GetMonitorInfoW.argtypes = [HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = BOOL
user32.EnumDisplayDevicesW.argtypes = [wt.LPCWSTR, DWORD, ctypes.POINTER(DISPLAY_DEVICEW), DWORD]
user32.EnumDisplayDevicesW.restype = BOOL
user32.EnumDisplaySettingsExW.argtypes = [wt.LPCWSTR, DWORD, ctypes.POINTER(DEVMODE), DWORD]
user32.EnumDisplaySettingsExW.restype = BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetDC.restype = HDC
user32.GetDC.argtypes = [HDC]
user32.ReleaseDC.argtypes = [HDC, HDC]
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
user32.RegisterClassExW.restype = wt.ATOM
user32.CreateWindowExW.restype = HWND
user32.CreateWindowExW.argtypes = [DWORD, wt.LPCWSTR, wt.LPCWSTR, DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, HWND, ctypes.c_void_p, HANDLE,
                                   ctypes.c_void_p]
user32.SetLayeredWindowAttributes.argtypes = [HWND, DWORD, ctypes.c_ubyte, DWORD]
user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, UINT]
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.UpdateWindow.argtypes = [HWND]
user32.DestroyWindow.argtypes = [HWND]
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.PostThreadMessageW.argtypes = [DWORD, UINT, WPARAM, LPARAM]
user32.PostThreadMessageW.restype = BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), HWND, UINT, UINT]
user32.GetMessageW.restype = BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
user32.GetWindowThreadProcessId.restype = DWORD
user32.GetShellWindow.argtypes = []
user32.GetShellWindow.restype = HWND
user32.GetWindowLongW.argtypes = [HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wt.LONG
user32.SetWindowLongW.argtypes = [HWND, ctypes.c_int, wt.LONG]
user32.SetWindowLongW.restype = wt.LONG
user32.LoadImageW.argtypes = [HANDLE, wt.LPCWSTR, UINT, ctypes.c_int, ctypes.c_int, UINT]
user32.LoadImageW.restype = HANDLE
user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = LRESULT
user32.GetDC.restype = HDC

kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = HANDLE
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = DWORD
kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

gdi32.CreateSolidBrush.restype = ctypes.c_void_p
gdi32.CreateSolidBrush.argtypes = [DWORD]
gdi32.CreateCompatibleDC.restype = HDC
gdi32.CreateCompatibleDC.argtypes = [HDC]
gdi32.CreateCompatibleBitmap.restype = HANDLE
gdi32.CreateCompatibleBitmap.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = HANDLE
gdi32.SelectObject.argtypes = [HDC, HANDLE]
gdi32.BitBlt.argtypes = [HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, HDC,
                         ctypes.c_int, ctypes.c_int, DWORD]
gdi32.StretchBlt.argtypes = [HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, HDC,
                             ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, DWORD]
gdi32.SetStretchBltMode.argtypes = [HDC, ctypes.c_int]
gdi32.SetStretchBltMode.restype = ctypes.c_int
gdi32.SetBrushOrgEx.argtypes = [HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
gdi32.SetBrushOrgEx.restype = BOOL
gdi32.GetDIBits.argtypes = [HDC, HANDLE, UINT, UINT, ctypes.c_void_p, ctypes.c_void_p, DWORD]
gdi32.GetDIBits.restype = BOOL
gdi32.DeleteObject.argtypes = [HANDLE]
gdi32.DeleteDC.argtypes = [HDC]

dwmapi.DwmSetWindowAttribute.argtypes = [HWND, DWORD, ctypes.c_void_p, DWORD]
dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = BOOL
dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [HANDLE, DWORD, ctypes.POINTER(PHYSICAL_MONITOR)]
dxva2.GetPhysicalMonitorsFromHMONITOR.restype = BOOL
dxva2.GetVCPFeatureAndVCPFeatureReply.argtypes = [HANDLE, ctypes.c_ubyte, ctypes.POINTER(DWORD),
                                                   ctypes.POINTER(DWORD)]
dxva2.GetVCPFeatureAndVCPFeatureReply.restype = BOOL
dxva2.SetVCPFeature.argtypes = [HANDLE, ctypes.c_ubyte, DWORD]
dxva2.SetVCPFeature.restype = BOOL
dxva2.DestroyPhysicalMonitors.argtypes = [DWORD, ctypes.POINTER(PHYSICAL_MONITOR)]
dxva2.DestroyPhysicalMonitors.restype = BOOL

#: Константы
MONITORINFOF_PRIMARY = 0x00000001
ENUM_CURRENT_SETTINGS = 0x00000001
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
LWA_ALPHA = 0x00000002
SWP_SHOWWINDOW = 0x0040
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
HALFTONE = 4

WM_APP = 0x8000
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_QUIT = 0x0012
WM_APP_APPLY = WM_APP + 1
WM_APP_STOP = WM_APP + 2


# --------------------------------------------------------- перечисление

def _iter_monitors():
    """Возвращает список (hmonitor, rect, is_primary)."""
    out: list[tuple[int, RECT, bool]] = []

    def callback(hmon, hdc, lprc, data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            out.append((int(ctypes.cast(hmon, ctypes.c_void_p).value or 0),
                        RECT.from_buffer_copy(info.rcMonitor),
                        bool(info.dwFlags & MONITORINFOF_PRIMARY)))
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    return out


def _iter_display_devices():
    """Список адаптеров: [{'name', 'string', 'flags', 'monitors': [...]}]."""
    adapters = []
    i = 0
    while True:
        dev = DISPLAY_DEVICEW()
        dev.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dev), 0):
            break
        entry = {
            "name": dev.DeviceName,
            "string": dev.DeviceString,
            "flags": int(dev.StateFlags),
            "monitors": [],
        }
        j = 0
        while True:
            mdev = DISPLAY_DEVICEW()
            mdev.cb = ctypes.sizeof(DISPLAY_DEVICEW)
            if not user32.EnumDisplayDevicesW(dev.DeviceName, j, ctypes.byref(mdev), 0):
                break
            entry["monitors"].append({
                "name": mdev.DeviceName,
                "string": mdev.DeviceString,
                "device_id": mdev.DeviceID,
                "flags": int(mdev.StateFlags),
            })
            j += 1
        adapters.append(entry)
        i += 1
    return adapters


def _display_mode(device_name: str):
    """
    Текущий режим отображения для GDI-устройства (позиция + разрешение).

    ENUM_CURRENT_SETTINGS для этой функции равен -1, а не 1 (единица означала
    бы «режим с индексом 1» и возвращала 640x480).
    """
    mode = DEVMODE()
    mode.dmSize = ctypes.sizeof(DEVMODE)
    if user32.EnumDisplaySettingsExW(device_name, -1, ctypes.byref(mode), 0):
        return mode
    return None


def enumerate_displays() -> list[dict]:
    """
    Собирает список активных дисплеев.

    Каждый элемент: dict(index, rect, gdi_name, device_id, is_primary,
    width, height, position).
    """
    displays: list[dict] = []
    adapters = _iter_display_devices()

    for adapter in adapters:
        mode = _display_mode(adapter["name"])
        if mode is None:
            continue
        if not (mode.dmPelsWidth and mode.dmPelsHeight):
            continue
        # У адаптера может быть несколько мониторов; берём первый
        monitor = adapter["monitors"][0] if adapter["monitors"] else {}
        displays.append({
            "gdi_name": adapter["name"],
            "adapter_string": adapter["string"],
            "device_id": monitor.get("device_id", ""),
            "monitor_string": monitor.get("string", ""),
            "rect": (mode.dmPosition.x, mode.dmPosition.y,
                     mode.dmPosition.x + mode.dmPelsWidth,
                     mode.dmPosition.y + mode.dmPelsHeight),
            "width": mode.dmPelsWidth,
            "height": mode.dmPelsHeight,
            "position": (mode.dmPosition.x, mode.dmPosition.y),
        })

    # Сопоставляем с реальными HMONITOR (проверяем координаты)
    for hmon, rect, is_primary in _iter_monitors():
        for disp in displays:
            if disp["rect"] == rect.as_tuple():
                disp["is_primary"] = is_primary
                disp["hmonitor"] = hmon
                break
        else:
            displays.append({
                "gdi_name": "", "adapter_string": "", "device_id": "",
                "monitor_string": "", "rect": rect.as_tuple(),
                "width": rect.width, "height": rect.height,
                "position": (rect.left, rect.top), "is_primary": is_primary,
                "hmonitor": hmon,
            })

    displays = [d for d in displays if "hmonitor" in d]
    displays.sort(key=lambda d: (not d.get("is_primary", False), d["position"]))
    for i, d in enumerate(displays):
        d["index"] = i
    return displays


def virtual_screen() -> tuple[int, int, int, int]:
    x = user32.GetSystemMetrics(76)
    y = user32.GetSystemMetrics(77)
    w = user32.GetSystemMetrics(78)
    h = user32.GetSystemMetrics(79)
    return x, y, w, h


# ------------------------------------------------------------------ DDC/CI

VCP_BRIGHTNESS = 0x10


class DdcMonitor:
    """
    Обёртка над физическим монитором (DXVA2) для чтения/записи VCP.

    Важно: массив PHYSICAL_MONITOR должен оставаться живым всё время
    работы с монитором — через него Windows связывает вызовы VCP
    с конкретным экраном.
    """

    def __init__(self, hmonitor: int):
        self.hmonitor = hmonitor
        self._array = None
        self._count = 0
        self._handle = None
        self.description = ""

    def open(self) -> bool:
        num = DWORD(0)
        if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(self.hmonitor, ctypes.byref(num)):
            return False
        if not num.value:
            return False
        array = (PHYSICAL_MONITOR * num.value)()
        if not dxva2.GetPhysicalMonitorsFromHMONITOR(self.hmonitor, num.value, array):
            return False
        self._array = array
        self._count = num.value
        self._handle = array[0].hPhysicalMonitor
        self.description = array[0].szPhysicalMonitorDescription or ""
        return True

    def close(self) -> None:
        if self._array is not None and self._count:
            try:
                dxva2.DestroyPhysicalMonitors(self._count, self._array)
            except Exception:
                pass
        self._array = None
        self._handle = None
        self._count = 0

    def read(self, code: int = VCP_BRIGHTNESS) -> tuple[int, int] | None:
        """Сырой ответ монитора: (первое_поле, второе_поле)."""
        if self._array is None:
            return None
        cur, mx = DWORD(0), DWORD(0)
        if not dxva2.GetVCPFeatureAndVCPFeatureReply(self._handle, code,
                                                      ctypes.byref(cur), ctypes.byref(mx)):
            return None
        return cur.value, mx.value

    def read_brightness(self) -> tuple[int, int | None] | None:
        """
        Возвращает (текущая яркость, максимум) или None.

        Часть мониторов (в т.ч. SAC2700) отдаёт ответ со сдвигом: первое
        поле всегда 1, а реальное значение яркости лежит во втором.
        Стандартные мониторы отдают (текущее, максимум) как есть.
        """
        raw = self.read(VCP_BRIGHTNESS)
        if raw is None:
            return None
        first, second = raw
        if first <= 1:
            return second, None
        return first, second

    def write(self, value: int, code: int = VCP_BRIGHTNESS) -> bool:
        if self._array is None:
            return False
        return bool(dxva2.SetVCPFeature(self._handle, code, int(value)))

    def discover_max(self, current: int) -> int:
        """
        Выясняет верхнюю границу яркости.

        Значение из монитора читается ненадёжно, поэтому проверяем границу
        пробой «+1»: если монитор обрезает значение, значит уже максимум.
        Проба незаметная — яркость меняется на один шаг.
        """
        if current >= 100:
            return 100
        self.write(current + 1)
        time.sleep(0.12)
        got = self.read_brightness()
        self.write(current)
        time.sleep(0.05)
        if got is None:
            return 100
        if got[0] <= current:
            # монитор обрезал значение — текущее и есть максимум
            return max(current, 1)
        # значение принимается: считаем шкалу стандартной 0..100
        return 100



# ----------------------------------------------------------------- оверлей

class _OverlayThread(threading.Thread):
    """
    Отдельный поток с циклом сообщений: держит по одному затемняющему
    окну на каждый монитор и применяет к ним прозрачность.
    """

    def __init__(self, rects: list[tuple[int, int, int, int]]):
        super().__init__(daemon=True, name="bloom-overlay")
        self._rects = rects
        self._lock = threading.Lock()
        self._levels: dict[int, int] = {i: 0 for i in range(len(rects))}
        self._windows: list[int] = []
        self._thread_id = 0
        self._ready = threading.Event()
        self._stop = False
        self._wc = None
        self._proc = None

    # --- API для внешнего потока ---
    def apply(self, levels: dict[int, int]) -> None:
        with self._lock:
            self._levels.update(levels)
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_APP_APPLY, 0, 0)

    def stop(self) -> None:
        self._stop = True
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_APP_STOP, 0, 0)

    # --- внутреннее ---
    def _create_windows(self) -> None:
        hinstance = kernel32.GetModuleHandleW(None)
        brush = gdi32.CreateSolidBrush(0x00000000)

        def wndproc(hwnd, msg, wparam, lparam):
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        # Важно: и класс окна, и обработчик должны жить всё время, пока
        # существуют окна — иначе ctypes освободит callback и Windows
        # упадёт при доставке сообщений.
        self._proc = WNDPROC(wndproc)
        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX)
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinstance
        wc.hbrBackground = brush
        wc.lpszClassName = "BloomDimOverlay"
        user32.RegisterClassExW(ctypes.byref(wc))
        self._wc = wc

        for rect in self._rects:
            x, y, r, b = rect
            hwnd = user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                "BloomDimOverlay", "Bloom overlay", WS_POPUP,
                x, y, r - x, b - y, None, None, hinstance, None,
            )
            self._windows.append(int(hwnd or 0))
            user32.SetLayeredWindowAttributes(hwnd, 0, 0, LWA_ALPHA)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, r - x, b - y,
                                SWP_SHOWWINDOW | SWP_NOACTIVATE)

    def _apply_locked(self) -> None:
        with self._lock:
            levels = dict(self._levels)
        for idx, hwnd in enumerate(self._windows):
            if not hwnd:
                continue
            dim = max(0, min(100, int(levels.get(idx, 0))))
            alpha = int(round(dim * 255 / 100))
            x, y, r, b = self._rects[idx]
            user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
            if alpha == 0:
                user32.ShowWindow(hwnd, 0)  # SW_HIDE
            else:
                user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, r - x, b - y,
                                    SWP_SHOWWINDOW | SWP_NOACTIVATE)
                user32.UpdateWindow(hwnd)

    def run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        self._create_windows()
        self._apply_locked()
        self._ready.set()

        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_APP_APPLY:
                self._apply_locked()
            elif msg.message == WM_APP_STOP:
                break
            else:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        for hwnd in self._windows:
            if hwnd:
                user32.DestroyWindow(hwnd)
        self._windows.clear()
        user32.PostQuitMessage(0)


class OverlayDimmer:
    """Управляет затемнением мониторов через полупрозрачные оверлеи."""

    def __init__(self, rects: list[tuple[int, int, int, int]]):
        self._rects = rects
        self._thread = _OverlayThread(rects)
        self._thread.start()
        self._thread._ready.wait(5.0)

    def set_dim(self, levels: dict[int, int]) -> None:
        """levels: {индекс_монитора: затемнение 0..100}."""
        self._thread.apply(levels)

    def close(self) -> None:
        self._thread.stop()
        self._thread.join(timeout=2.0)


# ------------------------------------------------------------------ скриншот

def capture_screen(rect: tuple[int, int, int, int], out_w: int, out_h: int,
                   dim: int = 0, radius: int = 0) -> bytes | None:
    """
    Снимает область экрана и возвращает PNG-байты размером out_w x out_h.

    dim (0..100) применяется к яркости прямо в пикселях — превью в
    интерфейсе показывает результат затемнения «как есть».
    radius скругляет углы прозрачной маской.
    """
    x, y, r, b = rect
    w, h = r - x, b - y
    if w <= 0 or h <= 0:
        return None

    screen_dc = user32.GetDC(None)
    if not screen_dc:
        return None

    # Шаг 1: копируем область на экранной DC.
    # Именно BitBlt, а не StretchBlt: он корректно работает с областями,
    # лежащими левее/выше начала координат виртуального экрана.
    # Битмапы создаём от экранной DC — у DC памяти формат по умолчанию
    # одноцветный, и цветное изображение в него не скопировать.
    src_dc = gdi32.CreateCompatibleDC(screen_dc)
    src_bmp = gdi32.CreateCompatibleBitmap(screen_dc, w, h)
    old_src = gdi32.SelectObject(src_dc, src_bmp)
    gdi32.BitBlt(src_dc, 0, 0, w, h, screen_dc, x, y, SRCCOPY | CAPTUREBLT)

    # Шаг 2: масштабируем в превью.
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, out_w, out_h)
    if not bitmap:
        gdi32.SelectObject(src_dc, old_src)
        gdi32.DeleteObject(src_bmp)
        gdi32.DeleteDC(src_dc)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
        return None

    old = gdi32.SelectObject(mem_dc, bitmap)
    gdi32.SetStretchBltMode(mem_dc, HALFTONE)
    # для HALFTONE обязателен сдвиг кисти, иначе режим не применяется
    gdi32.SetBrushOrgEx(mem_dc, 0, 0, None)
    gdi32.StretchBlt(mem_dc, 0, 0, out_w, out_h, src_dc, 0, 0, w, h, SRCCOPY)

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = out_w
    bi.bmiHeader.biHeight = -out_h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(out_w * out_h * 4)
    ok = gdi32.GetDIBits(mem_dc, bitmap, 0, out_h, buf, ctypes.byref(bi), 0)

    gdi32.SelectObject(mem_dc, old)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    gdi32.SelectObject(src_dc, old_src)
    gdi32.DeleteObject(src_bmp)
    gdi32.DeleteDC(src_dc)
    user32.ReleaseDC(None, screen_dc)

    if not ok:
        return None
    return _bgra_to_png(buf.raw, out_w, out_h, dim, radius)


def _bgra_to_png(raw: bytes, width: int, height: int, dim: int, radius: int = 0) -> bytes:
    """Конвертирует BGRA-буфер в PNG (RGBA), затемняя пиксели на dim процентов."""
    import struct
    import zlib

    factor = 1.0 - max(0, min(100, dim)) / 100.0
    rows = []
    stride = width * 4
    for y in range(height):
        base = y * stride
        row = bytearray()
        row.append(0)  # PNG filter type 0
        for x in range(width):
            i = base + x * 4
            b, g, r = raw[i], raw[i + 1], raw[i + 2]
            if factor < 1.0:
                r = int(r * factor)
                g = int(g * factor)
                b = int(b * factor)
            if radius > 0:
                alpha = _corner_alpha(x, y, width, height, radius)
            else:
                alpha = 255
            row += bytes((r, g, b, alpha))
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    payload = zlib.compress(b"".join(rows), 6)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", payload)
            + chunk(b"IEND", b""))


def _corner_alpha(x: int, y: int, width: int, height: int, radius: int) -> int:
    """Сглаженная альфа-маска по углам (суперимпозиция со сглаживанием)."""
    radius = min(radius, width // 2, height // 2)
    if radius <= 0:
        return 255
    cx = cy = None
    if x < radius and y < radius:
        cx, cy = radius, radius
    elif x >= width - radius and y < radius:
        cx, cy = width - radius - 1, radius
    elif x < radius and y >= height - radius:
        cx, cy = radius, height - radius - 1
    elif x >= width - radius and y >= height - radius:
        cx, cy = width - radius - 1, height - radius - 1
    if cx is None:
        return 255
    dist = math.hypot(x - cx, y - cy)
    if dist <= radius - 1:
        return 255
    if dist >= radius:
        return 0
    return int(round(255 * (radius - dist)))



# --------------------------------------------------------------- оформление

def enable_dpi_awareness() -> None:
    """Включает Per-Monitor DPI, чтобы интерфейс не мылился на 125%/150%."""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def style_window(hwnd: int) -> None:
    """Тёмный заголовок + скруглённые углы (Windows 11)."""
    # DWMWA_USE_IMMERSIVE_DARK_MODE (20) / DWMWA_WINDOW_CORNER_PREFERENCE (33)
    dark = ctypes.c_int(1)
    try:
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
    except Exception:
        pass
    try:
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


def set_process_dpi_for_tk() -> None:
    """Хелпер для вызова до создания окна Tk."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
