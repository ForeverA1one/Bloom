"""
Определение мониторов: EDID из реестра, человекочитаемые имена, привязка
к реальным дисплеям в системе.
"""

from __future__ import annotations

import winreg

from . import native


def _decode_manufacturer(b8: int, b9: int) -> str:
    """
    Трёхбуквенный код производителя из EDID (по 5 бит на букву).

    Раскладка как в ядре Linux (drivers/edid.c): первая буква берётся из
    битов 2..6 первого байта, вторая — из младших битов первого и старших
    второго, третья — из младших битов второго.
    """
    c1 = (b8 & 0x7C) >> 2
    c2 = ((b8 & 0x03) << 3) | ((b9 & 0x60) >> 5)
    c3 = b9 & 0x1F
    return "".join(chr(c + 64) for c in (c1, c2, c3))


def _descriptor_text(edid: bytes, tag: int) -> str | None:
    """Текстовый дескриптор EDID (тег 0xFC — имя монитора, 0xFE — серийник)."""
    for i in range(54, 126, 18):
        block = edid[i:i + 18]
        if len(block) < 18 or block[0] != 0x00 or block[1] != 0x00:
            continue
        if block[3] != tag:
            continue
        text = block[5:18].split(b"\x0a")[0].decode("ascii", "ignore").strip()
        return text or None
    return None


def _parse_edid(edid: bytes) -> dict | None:
    if len(edid) < 128 or edid[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return None
    manufacturer = _decode_manufacturer(edid[8], edid[9])
    product = int.from_bytes(edid[10:12], "little")
    name = _descriptor_text(edid, 0xFC)
    serial = _descriptor_text(edid, 0xFE)
    size_h = edid[21]
    size_v = edid[22]
    return {
        "manufacturer": manufacturer,
        "product": product,
        "code": f"{manufacturer}{product:04X}",
        "name": name,
        "serial": serial,
        "size": (size_h, size_v),
        "interface": _interface_name(edid),
    }


def _read_registry_edids() -> dict[str, dict]:
    """
    Читает EDID всех мониторов из реестра.

    Возвращает словарь: код монитора (например 'SAM08AB') -> параметры.
    """
    result: dict[str, dict] = {}
    root = r"SYSTEM\CurrentControlSet\Enum\DISPLAY"
    try:
        vendor_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root)
    except OSError:
        return result

    with vendor_key:
        vendors = []
        index = 0
        while True:
            try:
                vendors.append(winreg.EnumKey(vendor_key, index))
            except OSError:
                break
            index += 1

        for vendor in vendors:
            try:
                vkey = winreg.OpenKey(vendor_key, vendor)
            except OSError:
                continue
            with vkey:
                instances = []
                index = 0
                while True:
                    try:
                        instances.append(winreg.EnumKey(vkey, index))
                    except OSError:
                        break
                    index += 1

                for instance in instances:
                    try:
                        ikey = winreg.OpenKey(vkey, instance)
                    except OSError:
                        continue
                    with ikey:
                        try:
                            dkey = winreg.OpenKey(ikey, "Device Parameters")
                        except OSError:
                            continue
                        with dkey:
                            try:
                                data, _ = winreg.QueryValueEx(dkey, "EDID")
                            except OSError:
                                continue
                        if isinstance(data, list):
                            data = bytes(data)
                        info = _parse_edid(data)
                        if info:
                            result[info["code"].upper()] = info
                            # Запасной ключ — код из пути реестра (SAM08AB)
                            result.setdefault(instance.upper(), info)
    return result


_EDID_CACHE: dict[str, dict] | None = None


def edid_table() -> dict[str, dict]:
    global _EDID_CACHE
    if _EDID_CACHE is None:
        _EDID_CACHE = _read_registry_edids()
    return _EDID_CACHE


def _monitor_code(device_id: str) -> str:
    """Из 'MONITOR\\SAM08AB\\{...}' достаём код 'SAM08AB'."""
    parts = device_id.split("\\")
    if len(parts) >= 2 and parts[0].upper() == "MONITOR":
        return parts[1].upper()
    return ""


VENDORS = {
    "SAM": "Samsung", "DEL": "Dell", "ACR": "Acer", "AOC": "AOC", "MSI": "MSI",
    "PHL": "Philips", "GSM": "LG", "LGD": "LG", "HWP": "HP", "BNQ": "BenQ",
    "VSC": "ViewSonic", "LEN": "Lenovo", "SHP": "Sharp", "NEC": "NEC",
    "AUO": "AUO", "APP": "Apple", "HSD": "HannSpree", "IVM": "Iiyama",
}

INTERFACES = {
    0x01: "DVI",
    0x02: "HDMI",
    0x03: "HDMI",
    0x04: "MDDI",
    0x05: "DisplayPort",
    0x06: "DisplayPort",
    0x07: "DisplayPort",
    0x08: "DisplayPort",
}

#: Имена, которые монитор пишет в EDID вместо названия модели
_GENERIC_NAMES = {
    "dp1", "dp-1", "dp2", "dp-2", "hdmi1", "hdmi-1", "hdmi2", "hdmi-2",
    "dvi1", "dvi-1", "vga", "generic pnp monitor", "generic monitor",
    "monitor", "unknown", "default",
}


def _interface_name(edid: bytes) -> str:
    """
    Тип подключения из байта 0x14 (Video Input Definition).

    Бит 7 — признак цифрового сигнала, тип интерфейса лежит в битах 3..0
    (0 — тип не указан).
    """
    byte = edid[20]
    if not byte & 0x80:
        return "аналоговый"
    return INTERFACES.get(byte & 0x0F, "цифровой")


def _diagonal_inches(size_h: int, size_v: int) -> int:
    """Диагональ в дюймах по размеру в сантиметрах из EDID."""
    if not size_h or not size_v:
        return 0
    return int(round((size_h ** 2 + size_v ** 2) ** 0.5 / 2.54))


def describe(display: dict) -> tuple[str, str]:
    """
    Возвращает (заголовок, подпись) для карточки монитора.
    """
    table = edid_table()
    code = _monitor_code(display.get("device_id", ""))
    info = table.get(code)

    title = ""
    vendor = ""
    diagonal = 0
    interface = ""
    if info:
        name = (info.get("name") or "").strip()
        if name and name.lower() not in _GENERIC_NAMES:
            title = name
        vendor = VENDORS.get(info.get("manufacturer", "").upper(), "")
        diagonal = _diagonal_inches(*info.get("size", (0, 0)))
        interface = info.get("interface", "")

    if not title:
        if diagonal:
            title = f"Монитор {diagonal}\""
        else:
            title = f"Монитор {display.get('index', 0) + 1}"

    parts: list[str] = []
    if vendor:
        parts.append(vendor)
    if diagonal:
        parts.append(f"{diagonal}\"")
    width = display.get("width", 0)
    height = display.get("height", 0)
    if width and height:
        parts.append(f"{width}×{height}")
    if interface:
        parts.append(interface)
    if display.get("is_primary"):
        parts.append("основной")

    subtitle = " • ".join(parts)
    if not subtitle:
        subtitle = display.get("adapter_string", "")
    return title, subtitle


def collect_displays() -> list[dict]:
    """Список дисплеев с именами, готовый для интерфейса."""
    displays = native.enumerate_displays()
    for disp in displays:
        title, subtitle = describe(disp)
        disp["title"] = title
        disp["subtitle"] = subtitle
    return displays
