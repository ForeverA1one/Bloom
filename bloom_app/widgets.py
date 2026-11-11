"""
Собственные виджеты: скруглённые карточки, слайдер, кнопки, бейджи.

Всё рисуется на Canvas — так можно получить скруглённые углы, градиенты и
мягкие тени, которых нет в стандартном ttk.
"""

from __future__ import annotations

import base64
import math
import struct
import tkinter as tk
import zlib

from . import theme


def _png_rgba(width: int, height: int, pixels: bytes) -> bytes:
    """Собирает PNG из RGBA-буфера (строки без фильтра)."""
    stride = width * 4
    raw = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride] for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def _coverage(dx: float, dy: float, radius: float) -> int:
    """Сглаженное покрытие пикселя у скруглённого угла (0..255)."""
    if radius <= 0:
        return 255
    dist = math.hypot(dx, dy)
    if dist <= radius - 1:
        return 255
    if dist >= radius:
        return 0
    return max(0, min(255, int(round(255 * (radius - dist + 0.5)))))


def make_gradient(width: int, height: int, c1, c2) -> bytes:
    """PNG горизонтального градиента со скруглёнными концами."""
    width = max(2, width)
    radius = height / 2.0
    data = bytearray()
    for y in range(height):
        dy = 0.0
        if y < radius:
            dy = radius - y
        elif y > height - 1 - radius:
            dy = y - (height - 1 - radius)
        for x in range(width):
            dx = 0.0
            if x < radius:
                dx = radius - x
            elif x > width - 1 - radius:
                dx = x - (width - 1 - radius)
            alpha = 255 if (dx <= 0 or dy <= 0) else _coverage(dx, dy, radius)
            t = x / max(1, width - 1)
            data += bytes((
                int(c1[0] + (c2[0] - c1[0]) * t),
                int(c1[1] + (c2[1] - c1[1]) * t),
                int(c1[2] + (c2[2] - c1[2]) * t),
                alpha,
            ))
    return _png_rgba(width, height, bytes(data))


def make_thumb(size: int, core, ring, glow) -> bytes:
    """PNG круглого бегунка: белое ядро, цветное кольцо и мягкое свечение."""
    size = max(8, size)
    center = (size - 1) / 2.0
    core_r = size * 0.34
    ring_r = size * 0.44
    data = bytearray()
    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - center, y - center)
            if dist <= core_r - 0.5:
                data += bytes((core[0], core[1], core[2], 255))
            elif dist <= ring_r:
                edge = min(1.0, (dist - (core_r - 0.5)) / 1.5)
                data += bytes((
                    int(core[0] + (ring[0] - core[0]) * edge),
                    int(core[1] + (ring[1] - core[1]) * edge),
                    int(core[2] + (ring[2] - core[2]) * edge), 255))
            elif dist <= size / 2.0:
                fade = 1.0 - (dist - ring_r) / max(0.5, size / 2.0 - ring_r)
                alpha = int(round(70 * fade * fade))
                data += bytes((glow[0], glow[1], glow[2], alpha))
            else:
                data += bytes((0, 0, 0, 0))
    return _png_rgba(size, size, bytes(data))


def photo_from_png(master, png: bytes) -> tk.PhotoImage:
    """Создаёт PhotoImage из PNG-байтов."""
    return tk.PhotoImage(master=master, data=base64.b64encode(png).decode("ascii"))


def rounded_points(x1: float, y1: float, x2: float, y2: float, r: float,
                   steps: int = 10) -> list[float]:
    """Точки для create_polygon, образующие скруглённый прямоугольник."""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points: list[float] = []

    def arc(cx: float, cy: float, start: float, end: float) -> None:
        for i in range(steps + 1):
            angle = start + (end - start) * i / steps
            points.extend((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    arc(x2 - r, y1 + r, -math.pi / 2, 0)
    arc(x2 - r, y2 - r, 0, math.pi / 2)
    arc(x1 + r, y2 - r, math.pi / 2, math.pi)
    arc(x1 + r, y1 + r, math.pi, math.pi * 1.5)
    return points


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kwargs):
    """Скруглённый прямоугольник из полигона со сглаживанием."""
    pts = rounded_points(x1, y1, x2, y2, r)
    return canvas.create_polygon(pts, smooth=True, splinesteps=12, **kwargs)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def blend(color_a: str, color_b: str, t: float) -> str:
    """Смешивает два цвета: t=0 -> a, t=1 -> b."""
    ar, ag, ab = hex_to_rgb(color_a)
    br, bg, bb = hex_to_rgb(color_b)
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % (
        int(ar + (br - ar) * t),
        int(ag + (bg - ag) * t),
        int(ab + (bb - ab) * t),
    )


class Card(tk.Frame):
    """Карточка со скруглённым фоном и тонкой рамкой."""

    def __init__(self, master, width=320, height=420, radius=theme.CARD_RADIUS,
                 bg=theme.CARD, border=theme.CARD_LINE, **kwargs):
        super().__init__(master, bg=master.cget("bg"), width=width, height=height,
                         highlightthickness=0, bd=0, **kwargs)
        self._radius = radius
        self._bg = bg
        self._border = border
        self._hover = False
        self._body_window = None
        self._body_pad = (0, 0)
        self.canvas = tk.Canvas(self, width=width, height=height, bg=master.cget("bg"),
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Enter>", lambda e: self._set_hover(True))
        self.canvas.bind("<Leave>", lambda e: self._set_hover(False))

    def _on_resize(self, event) -> None:
        if self._body_window is not None:
            padx, pady = self._body_pad
            self.canvas.itemconfigure(self._body_window,
                                      width=max(1, event.width - padx * 2),
                                      height=max(1, event.height - pady * 2))
        self._redraw()

    def _set_hover(self, value: bool) -> None:
        if self._hover != value:
            self._hover = value
            self._redraw()

    def _redraw(self) -> None:
        w = self.canvas.winfo_width() or 1
        h = self.canvas.winfo_height() or 1
        self.canvas.delete("bg")
        line = blend(theme.CARD_LINE, theme.ACCENT, 0.35) if self._hover else theme.CARD_LINE
        round_rect(self.canvas, 1, 1, w - 1, h - 1, self._radius,
                   fill=self._bg, outline=line, width=1, tags="bg")
        # мягкая подсветка верхней кромки
        self.canvas.create_line(20, 1.5, w - 20, 1.5,
                                fill=blend(self._bg, "#FFFFFF", 0.07), tags="bg")

    def body(self, padx: int = 0, pady: int = 0) -> tk.Frame:
        """Контейнер для содержимого карточки (лежит поверх фона)."""
        self._body_pad = (padx, pady)
        frame = tk.Frame(self.canvas, bg=self._bg)
        self._body_window = self.canvas.create_window(padx, pady, window=frame, anchor="nw")
        self.canvas.tag_raise(self._body_window)
        return frame


class Badge(tk.Canvas):
    """Небольшая «пилюля» с текстом — используется для указания способа."""

    def __init__(self, master, text="", dot_color=theme.OK, text_color=theme.TEXT_DIM,
                 fonts=None, pad_x=10, pad_y=4, bg=theme.CARD):
        self.fonts = fonts
        super().__init__(master, bg=bg, highlightthickness=0, bd=0,
                         height=22, cursor="hand2")
        self._text = text
        self._dot = dot_color
        self._fg = text_color
        self._bg = bg
        self._pad_x = pad_x
        self._pad_y = pad_y
        self.bind("<Configure>", lambda e: self._redraw())

    def set(self, text: str, dot_color=None, text_color=None) -> None:
        self._text = text
        if dot_color:
            self._dot = dot_color
        if text_color:
            self._fg = text_color
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        font = self.fonts.badge if self.fonts else None
        w = self.winfo_width() or 1
        h = self.winfo_height() or 1
        if not self._text:
            self.configure(width=1)
            return
        text_w = (font.measure(self._text) if font else len(self._text) * 7)
        needed = text_w + self._pad_x * 2 + 22
        self.configure(width=needed)
        w = max(w, needed)
        cy = h / 2
        self.create_oval(self._pad_x, cy - 3, self._pad_x + 6, cy + 3,
                         fill=self._dot, outline="")
        self.create_text(self._pad_x + 13, cy, text=self._text, anchor="w",
                         fill=self._fg, font=font)


class FlatButton(tk.Canvas):
    """Плоская кнопка со скруглением и состоянием наведения."""

    def __init__(self, master, text="", command=None, fonts=None, width=92, height=32,
                 bg=theme.BG_DEEP, fg=theme.TEXT_DIM, hover_bg=theme.CARD_LINE,
                 hover_fg=theme.TEXT, radius=9, font=None):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, width=width,
                         height=height, cursor="hand2")
        self._text = text
        self._command = command
        self._font = font or (fonts.small_dim if fonts else None)
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._hover_fg = hover_fg
        self._radius = radius
        self._hover = False
        self._active = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._redraw())

    def configure_text(self, text: str) -> None:
        self._text = text
        self._redraw()

    def _on_enter(self, _event=None):
        self._hover = True
        self._redraw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._active = False
        self._redraw()

    def _on_press(self, _event=None):
        self._active = True
        self._redraw()

    def _on_release(self, _event=None):
        was_active = self._active
        self._active = False
        self._redraw()
        if was_active and self._command:
            self._command()

    def _redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width() or 1
        h = self.winfo_height() or 1
        bg = self._hover_bg if (self._hover or self._active) else self._bg
        fg = self._hover_fg if (self._hover or self._active) else self._fg
        round_rect(self, 1, 1, w - 1, h - 1, self._radius,
                   fill=bg, outline=theme.CARD_LINE, width=1)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)


class Slider(tk.Canvas):
    """
    Горизонтальный слайдер: дорожка с градиентной заливкой и «свечением»
    под бегунком. Перетаскивание мышью и управление стрелками.

    Заливка и бегунок рисуются готовыми PNG: примитивы Canvas не сглаживаются
    и выглядят «пиксельными».
    """

    def __init__(self, master, value=100, minimum=0, maximum=100, command=None,
                 fonts=None, bg=theme.CARD, height=34, radius=9):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, height=height,
                         cursor="hand2")
        self._value = value
        self._min = minimum
        self._max = maximum
        self._command = command
        self._bg = bg
        self._radius = radius
        self._dragging = False
        self._hover = False
        self._grad_cache: dict[int, tk.PhotoImage] = {}
        self._thumb_cache: dict[int, tk.PhotoImage] = {}

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self._redraw()))
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self._redraw()))
        self.bind("<FocusIn>", lambda e: self._redraw())
        self.bind("<FocusOut>", lambda e: self._redraw())
        self.bind("<Left>", lambda e: self._step(-5))
        self.bind("<Right>", lambda e: self._step(5))
        self.bind("<Home>", lambda e: self._set(self._min))
        self.bind("<End>", lambda e: self._set(self._max))
        self.bind("<Key>", lambda e: self.focus_set())
        self.takefocus = 1

    # ------------------------------------------------------------- состояние
    @property
    def value(self) -> int:
        return self._value

    def set(self, value: int, notify: bool = False) -> None:
        value = max(self._min, min(self._max, int(round(value))))
        if value != self._value:
            self._value = value
            self._redraw()
            if notify and self._command:
                self._command(value)
        else:
            self._redraw()

    def _set(self, value: int) -> None:
        value = max(self._min, min(self._max, int(round(value))))
        changed = value != self._value
        self._value = value
        self._redraw()
        if changed and self._command:
            self._command(value)

    def _step(self, delta: int) -> None:
        self._set(self._value + delta)
        return "break"

    # --------------------------------------------------------------- события
    def _value_at(self, x: int) -> int:
        width = self.winfo_width() or 1
        pad = 14
        span = max(1, width - pad * 2)
        ratio = (x - pad) / span
        ratio = max(0.0, min(1.0, ratio))
        return int(round(self._min + ratio * (self._max - self._min)))

    def _on_press(self, event) -> None:
        self.focus_set()
        self._dragging = True
        self._set(self._value_at(event.x))

    def _on_drag(self, event) -> None:
        if self._dragging:
            self._set(self._value_at(event.x))

    def _on_release(self, _event=None) -> None:
        self._dragging = False

    # -------------------------------------------------------------- отрисовка
    def _gradient(self, width: int, height: int) -> tk.PhotoImage:
        image = self._grad_cache.get(width)
        if image is None:
            image = photo_from_png(self, make_gradient(
                width, height, hex_to_rgb(theme.ACCENT), hex_to_rgb(theme.ACCENT_2)))
            self._grad_cache[width] = image
        return image

    def _thumb(self, size: int) -> tk.PhotoImage:
        image = self._thumb_cache.get(size)
        if image is None:
            image = photo_from_png(self, make_thumb(
                size, (255, 255, 255),
                hex_to_rgb(theme.ACCENT_2),
                hex_to_rgb(theme.ACCENT)))
            self._thumb_cache[size] = image
        return image

    def _redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width() or 1
        h = self.winfo_height() or 1
        pad = 14
        track_h = 8
        cy = h / 2
        x1, x2 = pad, w - pad

        # дорожка
        round_rect(self, x1, cy - track_h / 2, x2, cy + track_h / 2, track_h / 2,
                   fill=theme.TRACK, outline="")

        span = max(1, x2 - x1)
        filled = int(span * (self._value - self._min) / max(1, (self._max - self._min)))

        # заливка градиентом со скруглёнными концами
        if filled > 2:
            self.create_image(x1, cy, image=self._gradient(filled, track_h), anchor="w")

        # бегунок
        thumb_x = x1 + filled
        size = 28 if (self._hover or self._dragging) else 24
        self.create_image(thumb_x, cy, image=self._thumb(size))


class ValueReadout(tk.Canvas):
    """Крупное числовое значение яркости с подписью процента."""

    def __init__(self, master, fonts=None, bg=theme.CARD, color=theme.TEXT,
                 sub_color=theme.TEXT_FAINT, height=56):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, height=height)
        self._fonts = fonts
        self._bg = bg
        self._color = color
        self._sub = sub_color
        self._value = 100
        self.bind("<Configure>", lambda e: self._redraw())

    def set(self, value: int) -> None:
        self._value = value
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width() or 1
        h = self.winfo_height() or 1
        big = self._fonts.value if self._fonts else None
        small = self._fonts.small if self._fonts else None
        text = str(self._value)

        # моноширинный шрифт: считаем ширину по шагу одного символа,
        # иначе знак «%» наезжает на последнюю цифру
        if big:
            advance = big.measure("0")
            value_w = advance * len(text)
            pct_w = small.measure("%") if small else 10
        else:
            value_w = len(text) * 18
            pct_w = 10
        gap = 7
        total = value_w + gap + pct_w
        x = max(0, (w - total) / 2)

        self.create_text(x, h / 2, text=text, anchor="w", fill=self._color, font=big)
        self.create_text(x + value_w + gap, h / 2 + 10, text="%", anchor="w",
                         fill=self._sub, font=small)


class Divider(tk.Canvas):
    """Тонкая горизонтальная линия-разделитель."""

    def __init__(self, master, bg=theme.CARD, color=theme.DIVIDER):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, height=1)
        self._color = color
        self.bind("<Configure>", lambda e: self._redraw())

    def _redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width() or 1
        self.create_line(0, 0, w, 0, fill=self._color)
