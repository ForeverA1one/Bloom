"""
Движок яркости.

Для каждого монитора выбирается способ управления:
  * DDC/CI — настоящая аппаратная яркость (VCP 0x10), если монитор отвечает;
  * программный — затемняющий оверлей, если DDC/CI недоступен.

Решение принимается автоматически, но может быть переопределено.
"""

from __future__ import annotations

import threading

from . import displays as displays_mod
from . import native

METHOD_DDC = "ddc"
METHOD_SOFTWARE = "software"


class _DdcWriter(threading.Thread):
    """
    Фоновый писатель DDC/CI.

    Запись по DDC занимает около 60 мс, поэтому вызывать её из потока
    интерфейса нельзя — перетаскивание ползунка «залипнет». Запросы
    сливаются: для каждого монитора пишется только последнее значение.
    """

    def __init__(self):
        super().__init__(daemon=True, name="bloom-ddc")
        self._lock = threading.Lock()
        self._pending: dict[int, tuple[Monitor, int]] = {}
        self._wake = threading.Event()
        self._stop = False

    def submit(self, monitor: "Monitor", raw_value: int) -> None:
        with self._lock:
            self._pending[monitor.index] = (monitor, raw_value)
        self._wake.set()

    def stop(self) -> None:
        """Останавливает поток и дожидается его завершения.

        Ждать обязательно: пока писатель работает с VCP-хендлом, его
        нельзя закрывать — драйвер в этом случае может зависнуть.
        """
        self._stop = True
        self._wake.set()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=5.0)

    def run(self) -> None:
        while not self._stop:
            self._wake.wait(0.2)
            self._wake.clear()
            with self._lock:
                batch = list(self._pending.values())
                self._pending.clear()
            for monitor, raw in batch:
                if self._stop:
                    return
                try:
                    ok = monitor._ddc.write(raw) if monitor._ddc else False
                except Exception:
                    ok = False
                if ok:
                    monitor.ddc_current = raw
                else:
                    monitor.ddc_failed()


class Monitor:
    """Один монитор системы."""

    def __init__(self, display: dict):
        self.index: int = display["index"]
        self.rect: tuple[int, int, int, int] = display["rect"]
        self.title: str = display.get("title") or "Монитор"
        self.subtitle: str = display.get("subtitle") or ""
        self.is_primary: bool = display.get("is_primary", False)
        self.width: int = display.get("width", 0)
        self.height: int = display.get("height", 0)
        self.hmonitor: int = display.get("hmonitor", 0)

        self.method: str = METHOD_SOFTWARE
        self.level: int = 100          # текущая яркость, %
        self.ddc_max: int | None = None
        self.ddc_current: int | None = None
        self.ddc_error: str = ""
        self._ddc: native.DdcMonitor | None = None

    @property
    def method_label(self) -> str:
        return "DDC/CI" if self.method == METHOD_DDC else "Программно"

    @property
    def method_hint(self) -> str:
        if self.method == METHOD_DDC:
            return f"аппаратная яркость, шкала 0–{self.ddc_max or 100}"
        return "затемнение экранным оверлеем"

    def __repr__(self) -> str:  # pragma: no cover - для отладки
        return f"<Monitor {self.index} {self.title!r} {self.method}>"

    def ddc_failed(self) -> None:
        """Аппаратный канал отказал — переходим на программное затемнение."""
        self.method = METHOD_SOFTWARE
        self.ddc_error = "аппаратный канал недоступен"


class BrightnessEngine:
    """Управляет яркостью всех мониторов."""

    def __init__(self):
        self.monitors: list[Monitor] = []
        self._dimmer: native.OverlayDimmer | None = None
        self._lock = threading.RLock()
        self._listeners: list = []
        self._writer = _DdcWriter()
        self._writer.start()

    # ------------------------------------------------------------- события
    def add_listener(self, callback) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback(self)
            except Exception:
                pass

    # ---------------------------------------------------------- инициализация
    def initialize(self) -> list[Monitor]:
        """Обнаруживает мониторы и определяет доступный способ управления."""
        with self._lock:
            raw = displays_mod.collect_displays()
            self.monitors = [Monitor(d) for d in raw]

            for monitor in self.monitors:
                self._probe_ddc(monitor)

            self._dimmer = native.OverlayDimmer([m.rect for m in self.monitors])

            # Начальное состояние: для DDC — текущая яркость монитора,
            # для программного — без затемнения.
            for monitor in self.monitors:
                if monitor.method == METHOD_DDC and monitor.ddc_current is not None:
                    monitor.level = self._percent_from_raw(monitor, monitor.ddc_current)
                else:
                    monitor.level = 100
        return self.monitors

    def _probe_ddc(self, monitor: Monitor) -> None:
        """Пытается включить аппаратное управление для монитора."""
        ddc = native.DdcMonitor(monitor.hmonitor)
        if not ddc.open():
            monitor.method = METHOD_SOFTWARE
            monitor.ddc_error = "монитор не отвечает на DDC/CI"
            return

        info = ddc.read_brightness()
        if info is None:
            ddc.close()
            monitor.method = METHOD_SOFTWARE
            monitor.ddc_error = "монитор не отвечает на DDC/CI"
            return

        current, maximum = info
        if maximum is None:
            maximum = ddc.discover_max(current)

        monitor._ddc = ddc
        monitor.method = METHOD_DDC
        monitor.ddc_max = max(int(maximum), 1)
        monitor.ddc_current = current

    # ------------------------------------------------------------- значения
    def _percent_from_raw(self, monitor: Monitor, raw: int) -> int:
        maximum = monitor.ddc_max or 100
        return max(0, min(100, int(round(raw * 100 / maximum))))

    def _raw_from_percent(self, monitor: Monitor, percent: int) -> int:
        maximum = monitor.ddc_max or 100
        return max(0, min(maximum, int(round(percent * maximum / 100))))

    # ------------------------------------------------------------ управление
    def set_level(self, monitor: Monitor, percent: int, notify: bool = True) -> bool:
        """Устанавливает яркость монитора (0..100)."""
        percent = max(0, min(100, int(percent)))
        with self._lock:
            monitor.level = percent
            if monitor.method == METHOD_DDC and monitor._ddc is not None:
                # запись уходит в фоновый поток — UI не блокируется
                self._writer.submit(monitor, self._raw_from_percent(monitor, percent))
            else:
                self._apply_overlay()
        if notify:
            self._notify()
        return True

    def _apply_overlay(self) -> None:
        if self._dimmer is None:
            return
        levels = {}
        for monitor in self.monitors:
            if monitor.method == METHOD_SOFTWARE:
                levels[monitor.index] = 100 - monitor.level
        self._dimmer.set_dim(levels)

    def refresh(self) -> None:
        """Перечитывает состояние мониторов (например, после разблокировки)."""
        with self._lock:
            for monitor in self.monitors:
                if monitor.method == METHOD_DDC and monitor._ddc is not None:
                    info = monitor._ddc.read_brightness()
                    if info:
                        monitor.ddc_current = info[0]
                        monitor.level = self._percent_from_raw(monitor, info[0])
            self._apply_overlay()
        self._notify()

    def close(self) -> None:
        """Восстанавливает яркость и освобождает ресурсы."""
        self._writer.stop()
        with self._lock:
            if self._dimmer is not None:
                self._dimmer.set_dim({m.index: 0 for m in self.monitors})
                self._dimmer.close()
                self._dimmer = None
            for monitor in self.monitors:
                if monitor._ddc is not None:
                    monitor._ddc.close()
                    monitor._ddc = None


class DemoBrightnessEngine(BrightnessEngine):
    """
    Движок для демонстрации: вымышленные мониторы, реальное железо не трогается.

    Яркость меняется только в памяти — удобно для записи скриншотов и видео.
    """

    def __init__(self):
        super().__init__()
        self._writer.stop()  # реальные записи DDC не нужны

    def initialize(self) -> list[Monitor]:
        from . import demo

        with self._lock:
            self.monitors = []
            for index, spec in enumerate(demo.DEMO_SCREENS):
                monitor = Monitor({
                    "index": index,
                    "rect": (0, 0, spec["width"], spec["height"]),
                    "title": spec["title"],
                    "subtitle": "",
                    "is_primary": index == 0,
                    "width": spec["width"],
                    "height": spec["height"],
                    "hmonitor": 0,
                })
                monitor.method = spec["method"]
                monitor.ddc_max = 100
                monitor.ddc_current = 70 if spec["method"] == METHOD_DDC else None
                monitor.level = 70 if spec["method"] == METHOD_DDC else 100
                self.monitors.append(monitor)
        return self.monitors

    def set_level(self, monitor: Monitor, percent: int, notify: bool = True) -> bool:
        percent = max(0, min(100, int(percent)))
        with self._lock:
            monitor.level = percent
            if monitor.method == METHOD_DDC:
                monitor.ddc_current = percent
        if notify:
            self._notify()
        return True

    def close(self) -> None:
        pass
