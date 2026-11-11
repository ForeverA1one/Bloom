# -*- coding: utf-8 -*-
"""
Bloom — управление яркостью мониторов.

Точка входа. Запуск:

    python bloom.py            обычный режим
    python bloom.py --demo     демонстрация: вымышленные мониторы,
                               реальные экраны не затрагиваются
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bloom_app import app  # noqa: E402


def main() -> None:
    demo = "--demo" in sys.argv[1:]
    app.run(demo=demo)


if __name__ == "__main__":
    main()
