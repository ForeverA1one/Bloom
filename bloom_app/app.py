"""
Главное окно приложения Bloom.

Тёмная тема — единственная. Окно без системной рамки, с собственной
шапкой, карточками на каждый монитор и живыми превью экранов.
"""

from __future__ import annotations

import base64
import queue
import sys
import threading
import time
import tkinter as tk

from . import engine, native, theme, widgets

WINDOW_WIDTH = 880
WINDOW_HEIGHT = 462
CARD_WIDTH = 372
CARD_HEIGHT = 400
PREVIEW_WIDTH = 328
APP_TITLE = "Bloom"


class MonitorCard(widgets.Card):
    """Карточка одного монитора: превью, значение, слайдер, пресеты."""

    def __init__(self, master, monitor: engine.Monitor, fonts, on_change):
        super().__init__(master, width=CARD_WIDTH, height=CARD_HEIGHT, bg=theme.CARD)
        self.monitor = monitor
        self.fonts = fonts
        self._on_change = on_change
        self._preview_image = None

        body = self.body(padx=theme.PAD, pady=18)
        body.pack_propagate(False)

        # --- заголовок ---
        head = tk.Frame(body, bg=theme.CARD)
        head.pack(fill="x")

        # Бейдж пакуется первым: иначе растягивающийся заголовок
        # вытеснит его и текст обрежется.
        self.badge = widgets.Badge(head, text=monitor.method_label, fonts=fonts,
                                   dot_color=theme.OK if monitor.method == engine.METHOD_DDC else theme.WARN,
                                   text_color=theme.TEXT_DIM)
        self.badge.pack(side="right", anchor="n")

        title_box = tk.Frame(head, bg=theme.CARD)
        title_box.pack(side="left", fill="x", expand=True)

        self.title_label = tk.Label(title_box, text=monitor.title, bg=theme.CARD,
                                    fg=theme.TEXT, font=fonts.h2, anchor="w")
        self.title_label.pack(anchor="w")

        # --- превью ---
        preview_w = PREVIEW_WIDTH
        preview_h = max(100, int(preview_w * monitor.height / max(1, monitor.width)))
        preview_holder = tk.Frame(body, bg=theme.CARD)
        preview_holder.pack(pady=(16, 0))

        self.preview = tk.Label(preview_holder, bg=theme.CARD, bd=0, highlightthickness=0)
        self.preview.pack()

        # --- значение ---
        self.value = widgets.ValueReadout(body, fonts=fonts, bg=theme.CARD)
        self.value.set(monitor.level)
        self.value.pack(pady=(8, 0))

        # --- слайдер ---
        self.slider = widgets.Slider(body, value=monitor.level, fonts=fonts, bg=theme.CARD,
                                     command=self._slider_changed)
        self.slider.pack(fill="x", pady=(2, 10))

        # --- пресеты ---
        presets = tk.Frame(body, bg=theme.CARD)
        presets.pack(fill="x")

        for value, label in ((100, "100%"), (60, "60%"), (30, "30%"), (0, "0%")):
            btn = widgets.FlatButton(presets, text=label, fonts=fonts, width=64, height=28,
                                      bg=theme.CARD, fg=theme.TEXT_DIM,
                                      hover_bg=theme.CARD_LINE, hover_fg=theme.TEXT,
                                      command=lambda v=value: self._preset(v))
            btn.pack(side="left", padx=(0, 8))

    def _preset(self, value: int) -> None:
        self.slider.set(value, notify=True)

    def _slider_changed(self, value: int) -> None:
        self.value.set(value)
        self._on_change(self.monitor, value)

    def _sync_hint(self) -> None:
        """Заглушка: подписи под превью убраны, метод отображается бейджем."""

    def _sync_hint(self) -> None:
        """Заглушка: подписи под превью убраны, метод отображается бейджем."""

    def update_state(self) -> None:
        """Обновляет бейдж и положение слайдера."""
        self.badge.set(self.monitor.method_label,
                       dot_color=theme.OK if self.monitor.method == engine.METHOD_DDC else theme.WARN)
        self.value.set(self.monitor.level)
        self.slider.set(self.monitor.level)

    def set_preview(self, png: bytes) -> None:
        try:
            image = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
        except Exception:
            return
        self._preview_image = image
        self.preview.configure(image=image)


class BloomApp:
    """Сборка окна и связывание с движком яркости."""

    def __init__(self, root: tk.Tk, demo: bool = False):
        self.root = root
        self.demo = demo
        self.engine = (engine.DemoBrightnessEngine() if demo else engine.BrightnessEngine())
        self.fonts = theme.Fonts(root)
        self.cards: list[MonitorCard] = []
        self._preview_queue: queue.Queue = queue.Queue()
        self._ready_queue: queue.Queue = queue.Queue()
        self._closing = False
        self._stop_preview = threading.Event()
        self._drag_offset = (0, 0)

        self._configure_window()
        self._build_ui()

        threading.Thread(target=self._initialize_engine, daemon=True,
                         name="bloom-init").start()

        self.root.after(120, self._poll_previews)

    # ------------------------------------------------------------- окно
    def _configure_window(self) -> None:
        self.root.title(APP_TITLE)
        self.root.configure(bg=theme.BG)
        self.root.resizable(False, False)
        self._apply_geometry(WINDOW_WIDTH)

        self.root.overrideredirect(True)
        hwnd = int(self.root.frame(), 16) if isinstance(self.root.frame(), str) else self.root.winfo_id()
        try:
            ex = native.user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
            native.user32.SetWindowLongW(hwnd, -20, ex | 0x00040000)  # WS_EX_APPWINDOW
        except Exception:
            pass
        native.style_window(hwnd)

        # без этого окно не реагирует на Alt+F4 и закрытие через панель задач
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _apply_geometry(self, width: int) -> None:
        """Ставит окно по центру основного монитора."""
        height = WINDOW_HEIGHT
        x = y = 0
        try:
            displays = native.enumerate_displays()
            primary = next((d for d in displays if d.get("is_primary")), None)
            if primary is None and displays:
                primary = displays[0]
            if primary:
                left, top, right, bottom = primary["rect"]
                x = left + (right - left - width) // 2
                y = top + (bottom - top - height) // 2
        except Exception:
            pass
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    # --------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=theme.BG)
        shell.pack(fill="both", expand=True)

        self._build_header(shell)

        content = tk.Frame(shell, bg=theme.BG_DEEP)
        content.pack(fill="both", expand=True)

        cards_area = tk.Frame(content, bg=theme.BG_DEEP)
        cards_area.pack(fill="x", padx=theme.PAD + 6, pady=(6, 0))

        # ряд карточек по центру, независимо от их количества
        self.cards_wrap = tk.Frame(cards_area, bg=theme.BG_DEEP)
        self.cards_wrap.pack(anchor="n")

        self._build_footer(content)

    def _build_header(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=theme.BG, height=22)
        header.pack(fill="x", pady=(10, 0))
        header.pack_propagate(False)

        # название по центру — как в Discord
        center = tk.Frame(header, bg=theme.BG)
        tk.Label(center, text=APP_TITLE, bg=theme.BG, fg=theme.TEXT,
                 font=self.fonts.h1).pack()
        center.place(relx=0.5, rely=0.5, anchor="center")

        # кнопка закрытия справа
        close = tk.Label(header, text="✕", bg=theme.BG, fg=theme.TEXT_DIM,
                         font=self.fonts.h3, cursor="hand2")

        def enter(_e=None):
            close.configure(bg=theme.CARD_LINE, fg=theme.TEXT)

        def leave(_e=None):
            close.configure(bg=theme.BG, fg=theme.TEXT_DIM)

        close.bind("<Enter>", enter)
        close.bind("<Leave>", leave)
        close.bind("<Button-1>", lambda e: self._close())
        close.place(relx=1.0, x=-16, rely=0.5, anchor="e")

        # перетаскивание окна мышью
        for widget in (header, center):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
        for label in center.winfo_children():
            label.bind("<Button-1>", self._drag_start)
            label.bind("<B1-Motion>", self._drag_move)

    def _build_footer(self, parent: tk.Frame) -> None:
        """Подвал убран: мелкие подписи только мешали."""
        return

    # --------------------------------------------------------- перетаскивание
    def _drag_start(self, event) -> None:
        self._drag_offset = (event.x_root - self.root.winfo_x(),
                             event.y_root - self.root.winfo_y())

    def _drag_move(self, event) -> None:
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    # -------------------------------------------------------------- движок
    def _initialize_engine(self) -> None:
        # Определение мониторов идёт в фоновом потоке, но трогать Tk
        # из него нельзя — результат отдаём через очередь, её разбирает
        # главный поток в _poll_previews.
        try:
            monitors = self.engine.initialize()
        except Exception as exc:  # pragma: no cover
            print(f"Ошибка определения мониторов: {exc}", file=sys.stderr)
            return

        self._ready_queue.put(monitors)
        self._start_preview_worker()

    def _on_monitors_ready(self, monitors) -> None:
        for child in self.cards_wrap.winfo_children():
            child.destroy()
        self.cards.clear()

        for monitor in monitors:
            card = MonitorCard(self.cards_wrap, monitor, self.fonts, self._on_card_change)
            card.pack(side="left", padx=(0, theme.GAP))
            self.cards.append(card)

        if not monitors:
            return

        # ширина окна подстраивается под число мониторов
        count = len(monitors)
        width = 2 * theme.PAD + 12 + count * CARD_WIDTH + (count - 1) * theme.GAP
        self._apply_geometry(min(width, 1600))

    def _on_card_change(self, monitor: engine.Monitor, value: int) -> None:
        self.engine.set_level(monitor, value)

    # ------------------------------------------------------------- превью
    def _start_preview_worker(self) -> None:
        """
        Живое превью.

        Частота кадров подстраивается сама: после каждого цикла измеряется
        затраченное время и пауза подбирается так, чтобы съёмка занимала
        примерно пятую часть процессорного времени. На быстром компьютере
        выходит около 8-10 кадров в секунду, на слабом — меньше, но интерфейс
        не будет подтормаживать.
        """
        grabbers: dict[int, native.ScreenGrabber] = {}

        def worker():
            while not self._closing:
                cycle_start = time.perf_counter()
                for monitor in list(self.engine.monitors):
                    if self._closing:
                        break
                    level = monitor.level
                    width = PREVIEW_WIDTH
                    height = max(100, int(width * monitor.height / max(1, monitor.width)))
                    # превью показывает, насколько ярким будет выглядеть экран
                    dim = 100 - level
                    png = None
                    try:
                        if self.demo:
                            from . import demo
                            png = demo.render_preview(monitor.index, width, height,
                                                      dim=dim, phase=time.monotonic())
                        else:
                            grabber = grabbers.get(monitor.index)
                            if grabber is None:
                                grabber = native.ScreenGrabber(monitor.rect)
                                grabbers[monitor.index] = grabber
                            png = grabber.grab(width, height, dim=dim, radius=14)
                    except Exception:
                        png = None
                    if png:
                        self._preview_queue.put((monitor.index, png))

                cycle = time.perf_counter() - cycle_start
                pause = max(0.09, min(1.5, cycle * 4))
                self._stop_preview.wait(pause)

        self._stop_preview = threading.Event()
        threading.Thread(target=worker, daemon=True, name="bloom-preview").start()

    def _poll_previews(self) -> None:
        # карточки появляются, когда фоновый поток закончит обследование
        while True:
            try:
                monitors = self._ready_queue.get_nowait()
            except queue.Empty:
                break
            self._on_monitors_ready(monitors)

        while True:
            try:
                index, png = self._preview_queue.get_nowait()
            except queue.Empty:
                break
            for card in self.cards:
                if card.monitor.index == index:
                    card.set_preview(png)
                    break
        if not self._closing:
            self.root.after(120, self._poll_previews)

    # -------------------------------------------------------------- выход
    def _close(self) -> None:
        self._closing = True
        self._stop_preview.set()
        try:
            self.engine.close()
        except Exception:
            pass
        self.root.destroy()


def run(demo: bool = False) -> None:
    native.enable_dpi_awareness()
    root = tk.Tk()
    app = BloomApp(root, demo=demo)
    root.mainloop()
