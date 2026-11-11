# -*- coding: utf-8 -*-
"""
Диагностика мониторов: что видно через DDC/CI, какая шкала яркости,
какой EDID и физический размер.

Запуск:  python probe_monitor.py
"""

import sys

from bloom_app import native
from bloom_app.displays import collect_displays


def main() -> None:
    # консоль по умолчанию cp1251 — переключаем на UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    displays = collect_displays()
    print(f"Найдено дисплеев: {len(displays)}\n")

    for disp in displays:
        x, y, r, b = disp["rect"]
        print("=" * 62)
        print(f"[{disp['index']}] {disp['title']}")
        print(f"    описание : {disp['subtitle']}")
        print(f"    EDID     : {disp['device_id']}")
        print(f"    область  : ({x}, {y}) — ({r}, {b})  {disp['width']}x{disp['height']}")
        print(f"    основной : {disp.get('is_primary')}")

        ddc = native.DdcMonitor(disp["hmonitor"])
        if not ddc.open():
            print("    DDC/CI   : монитор не отвечает")
            continue

        print(f"    DDC/CI   : описание «{ddc.description or '—'}»")
        info = ddc.read_brightness()
        if info is None:
            print("    яркость  : не читается (VCP 0x10)")
        else:
            current, maximum = info
            print(f"    яркость  : текущее {current}"
                  + (f", максимум {maximum}" if maximum else ", максимум неизвестен"))
            if maximum is None:
                maximum = ddc.discover_max(current)
                print(f"    шкала    : определена как 0..{maximum}")
        ddc.close()
        print()


if __name__ == "__main__":
    sys.exit(main())
