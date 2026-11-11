# -*- coding: utf-8 -*-
"""
Яркость мониторов — совместимая точка входа.

Актуальная реализация живёт в пакете `lumen_app`, запускается файлом
`lumen.py`. Этот скрипт оставлен для тех, кто запускал прежнюю версию.

Запуск:  python brightness_slider.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bloom_app import app  # noqa: E402


if __name__ == "__main__":
    app.run()
