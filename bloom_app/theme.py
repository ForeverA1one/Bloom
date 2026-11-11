"""
Оформление: палитра, типографика, метрики.

Приложение существует только в тёмной теме — светлых вариантов нет
и не предусмотрено.
"""

from __future__ import annotations

import tkinter.font as tkfont

# ------------------------------------------------------------------ цвета
BG = "#07090D"            # фон окна
BG_DEEP = "#0B0E14"       # фон рабочей области
CARD = "#12161F"          # карточка монитора
CARD_LINE = "#212836"     # граница карточки
DIVIDER = "#1C2230"

TRACK = "#1E2431"         # дорожка слайдера
TRACK_FILL = "#202636"

TEXT = "#EDF1F8"          # основной текст
TEXT_DIM = "#93A0B8"      # вторичный текст
TEXT_FAINT = "#5C6880"    # подписи

ACCENT = "#7C6CFF"        # фиолетовый
ACCENT_2 = "#22D3EE"      # бирюзовый
ACCENT_SOFT = "#3A3560"

OK = "#34D399"
WARN = "#FBBF24"
BAD = "#F87171"

SHADOW = "#030407"

# --------------------------------------------------------------- типографика
_FAMILY_DISPLAY = ("Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI", "Tahoma")
_FAMILY_TEXT = ("Segoe UI Variable Text", "Segoe UI", "Tahoma")
_FAMILY_MONO = ("Cascadia Mono", "Consolas", "Courier New")
_FAMILY_ICON = ("Segoe Fluent Icons", "Segoe MDL2 Assets", "Segoe UI Symbol")


def pick_family(root, candidates: tuple[str, ...]) -> str:
    """Первый доступный шрифт из списка."""
    available = set(tkfont.families(root))
    for name in candidates:
        if name in available:
            return name
    return candidates[-1]


class Fonts:
    """Ленивый набор шрифтов под конкретное окно."""

    def __init__(self, root):
        self.display = pick_family(root, _FAMILY_DISPLAY)
        self.text = pick_family(root, _FAMILY_TEXT)
        self.mono = pick_family(root, _FAMILY_MONO)
        self.icon = pick_family(root, _FAMILY_ICON)

        self.h1 = tkfont.Font(root=root, family=self.display, size=15, weight="bold")
        self.h2 = tkfont.Font(root=root, family=self.display, size=15, weight="bold")
        self.h3 = tkfont.Font(root=root, family=self.display, size=12, weight="bold")
        self.body = tkfont.Font(root=root, family=self.text, size=10)
        self.body_dim = tkfont.Font(root=root, family=self.text, size=10, weight="bold")
        self.small = tkfont.Font(root=root, family=self.text, size=9)
        self.small_dim = tkfont.Font(root=root, family=self.text, size=9, weight="bold")
        self.tiny = tkfont.Font(root=root, family=self.text, size=8)
        self.value = tkfont.Font(root=root, family=self.mono, size=30, weight="bold")
        self.value_small = tkfont.Font(root=root, family=self.mono, size=15, weight="bold")
        self.badge = tkfont.Font(root=root, family=self.text, size=9, weight="bold")


# ----------------------------------------------------------------- метрики
RADIUS = 16
CARD_RADIUS = 20
GAP = 18
PAD = 22
