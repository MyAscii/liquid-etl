from __future__ import annotations

from typing import List, Optional


def extract_op_return_data_hex(script_hex: Optional[str]) -> Optional[str]:
    if not script_hex:
        return None
    hx = script_hex.strip().lower()
    if hx.startswith("0x"):
        hx = hx[2:]
    if len(hx) < 2 or hx[:2] != "6a":
        return None
    try:
        b = bytes.fromhex(hx)
    except Exception:
        return None

    if len(b) == 1:
        return ""

    i = 1
    op = b[i]
    i += 1
    if op <= 75:
        ln = op
    elif op == 76:
        if i >= len(b):
            return None
        ln = b[i]
        i += 1
    elif op == 77:
        if i + 1 >= len(b):
            return None
        ln = int.from_bytes(b[i : i + 2], "little")
        i += 2
    elif op == 78:
        if i + 3 >= len(b):
            return None
        ln = int.from_bytes(b[i : i + 4], "little")
        i += 4
    else:
        return None

    if i + ln > len(b):
        return None
    return b[i : i + ln].hex()


def disassemble_script(script_hex: Optional[str]) -> Optional[str]:
    if not script_hex:
        return None
    hx = script_hex.strip().lower()
    if hx.startswith("0x"):
        hx = hx[2:]
    try:
        b = bytes.fromhex(hx)
    except Exception:
        return None

    out: List[str] = []
    i = 0
    while i < len(b):
        op = b[i]
        i += 1

        if op == 0x00:
            out.append("OP_0")
            continue
        if 0x51 <= op <= 0x60:
            out.append(f"OP_{op - 0x50}")
            continue
        if op == 0x6A:
            out.append("OP_RETURN")
            continue

        if 1 <= op <= 75:
            ln = op
            if i + ln > len(b):
                return None
            data = b[i : i + ln]
            i += ln
            out.append(f"OP_PUSHBYTES_{ln}")
            out.append(data.hex().upper())
            continue
        if op == 76:
            if i >= len(b):
                return None
            ln = b[i]
            i += 1
            if i + ln > len(b):
                return None
            data = b[i : i + ln]
            i += ln
            out.append("OP_PUSHDATA1")
            out.append(data.hex().upper())
            continue
        if op == 77:
            if i + 1 >= len(b):
                return None
            ln = int.from_bytes(b[i : i + 2], "little")
            i += 2
            if i + ln > len(b):
                return None
            data = b[i : i + ln]
            i += ln
            out.append("OP_PUSHDATA2")
            out.append(data.hex().upper())
            continue
        if op == 78:
            if i + 3 >= len(b):
                return None
            ln = int.from_bytes(b[i : i + 4], "little")
            i += 4
            if i + ln > len(b):
                return None
            data = b[i : i + ln]
            i += ln
            out.append("OP_PUSHDATA4")
            out.append(data.hex().upper())
            continue

        out.append(f"OP_UNKNOWN_0x{op:02X}")

    return " ".join(out) if out else ""
