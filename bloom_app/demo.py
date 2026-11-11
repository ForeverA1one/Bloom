"""
Демонстрационный режим.

Нужен, чтобы показывать интерфейс (скриншоты, запись видео) не трогая
реальные мониторы: вместо них используются вымышленные экраны с
анимированными превью. Реальный DDC/CI и оверлеи в этом режиме не
задействуются.
"""

from __future__ import annotations

import math
import struct
import zlib

METHOD_DDC = "ddc"
METHOD_SOFTWARE = "software"

#: Вымышленные мониторы: название, разрешение, способ управления, палитра
DEMO_SCREENS = [
    {
        "title": "Монитор 1",
        "width": 2560,
        "height": 1440,
        "method": METHOD_DDC,
        "palette": ((14, 17, 34), (74, 62, 178), (120, 96, 255)),
    },
    {
        "title": "Монитор 2",
        "width": 1920,
        "height": 1080,
        "method": METHOD_SOFTWARE,
        "palette": ((10, 20, 28), (22, 96, 116), (64, 214, 196)),
    },
]


def _png(width: int, height: int, rows: list[bytearray]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))


def _rect(rows: list[bytearray], width: int, height: int,
          x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int]) -> None:
    """Заливает прямоугольник цветом."""
    x1, x2 = max(0, min(x1, x2)), min(width, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(height, max(y1, y2))
    if x1 >= x2 or y1 >= y2:
        return
    line = bytes(color) * (x2 - x1)
    for y in range(y1, y2):
        rows[y][x1 * 3:x2 * 3] = line


def render_preview(index: int, width: int, height: int,
                   dim: int = 0, phase: float = 0.0) -> bytes:
    """
    Рисует анимированное превью «экрана» и возвращает PNG.

    phase — время в секундах: по нему двигаются волна и блики, поэтому
    картинка выглядит как видео, а не как статичная картинка.

    dim (0..100) затемняет картинку — так же, как это делает настоящий
    экран, поэтому по превью видно эффект изменения яркости.
    """
    spec = DEMO_SCREENS[index % len(DEMO_SCREENS)]
    top_color, mid_color, accent = spec["palette"]

    factor = 1.0 - max(0, min(100, dim)) / 100.0
    top = _shade(top_color, factor)
    mid = _shade(mid_color, factor)
    glow = _shade(accent, factor)
    panel = _shade((18, 22, 34), factor)
    panel_line = _shade((44, 52, 72), factor)
    dimmed_text = _shade((74, 84, 110), factor)

    rows: list[bytearray] = []
    # фон: вертикальный градиент + бегущая световая полоса
    band_y = int((phase * 0.22) % 1.4 * height) - height // 8
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(top[i] + (mid[i] - top[i]) * t) for i in range(3))
        near = max(0.0, 1.0 - abs(y - band_y) / max(6.0, height * 0.18))
        if near > 0:
            color = tuple(int(c + (glow[i] - c) * near * 0.45) for i, c in enumerate(color))
        rows.append(bytearray(bytes(color) * width))

    # окно «медиаплеера»
    wx1, wy1 = int(width * 0.07), int(height * 0.10)
    wx2, wy2 = int(width * 0.93), int(height * 0.90)
    _rect(rows, width, height, wx1, wy1, wx2, wy2, panel)
    _rect(rows, width, height, wx1, wy1, wx2, wy1 + max(3, height // 26), glow)
    _rect(rows, width, height, wx1 + 8, wy1 + 12, wx1 + 8 + int((wx2 - wx1) * 0.28),
          wy1 + 12 + max(2, height // 60), dimmed_text)

    # бегущая полоса прокрутки
    track_x1, track_x2 = wx1 + 10, wx2 - 10
    track_y = wy2 - max(8, height // 16)
    _rect(rows, width, height, track_x1, track_y, track_x2, track_y + 2, panel_line)
    knob = track_x1 + int((track_x2 - track_x1) * ((phase * 0.18) % 1.0))
    _rect(rows, width, height, knob, track_y - 2, knob + max(5, width // 60),
          track_y + 4, glow)

    # звуковая дорожка: столбики, плавно меняющие высоту
    base_y = wy2 - max(12, height // 12)
    amp = max(6, (base_y - wy1 - height // 10) // 2)
    bar_w = max(2, width // 120)
    step = max(3, width // 64)
    x = wx1 + 12
    while x < wx2 - 14:
        wave = (math.sin(x * 0.085 + phase * 3.1)
                + 0.55 * math.sin(x * 0.031 - phase * 1.7)
                + 0.35 * math.sin(phase * 2.3 + x * 0.011))
        h = int(amp * (0.30 + 0.30 * wave))
        if h > 1:
            _rect(rows, width, height, x, base_y - h, x + bar_w, base_y, glow)
        x += step

    # бегущие точки-индикаторы
    for i in range(5):
        t = (phase * 0.6 + i * 0.2) % 1.0
        px = int(wx1 + (wx2 - wx1 - 10) * t)
        py = wy1 + max(10, height // 12)
        _rect(rows, width, height, px, py, px + max(3, width // 90),
              py + max(3, width // 90), glow)

    return _png(width, height, rows)
